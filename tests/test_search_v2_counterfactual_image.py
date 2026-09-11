import ast
import hashlib
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.search_v2.counterfactual_image import COUNTERFACTUAL_RANKING_ENABLED
from src.search_v2.counterfactual_image import CounterfactualImageError
from src.search_v2.counterfactual_image import CounterfactualReferenceSet
from src.search_v2.counterfactual_image import VisualConditionSet
from src.search_v2.counterfactual_image import VisualConditionDraft
from src.search_v2.counterfactual_image import build_counterfactual_reference_set
from src.search_v2.counterfactual_image import build_visual_condition_set
from src.search_v2.counterfactual_image import counterfactual_reference_set_sha256
from src.search_v2.counterfactual_image import counterfactual_score_profile_sha256
from src.search_v2.counterfactual_image import score_counterfactual_conditions
from src.search_v2.counterfactual_image import visual_condition_set_sha256
from src.search_v2.image_similarity import CLIP_EMBEDDING_DIMENSION
from src.search_v2.image_similarity import ClipEmbedding
from src.search_v2.image_similarity import ImagePerceptualHash
from src.search_v2.image_similarity import clip_runtime_profile_sha256


def draft(
    phrase: str,
    *,
    strength: str = "required",
    attribute_key: str | None = None,
) -> VisualConditionDraft:
    return VisualConditionDraft.model_validate(
        {
            "source_phrase": phrase,
            "strength": strength,
            "attribute_key": attribute_key,
        }
    )


def image_hash(tag: str, value: int) -> ImagePerceptualHash:
    return ImagePerceptualHash(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(tag.encode()).hexdigest(),
        value=value,
    )


def unit_vector(*components: float) -> tuple[float, ...]:
    norm = math.sqrt(math.fsum(value * value for value in components))
    values = [value / norm for value in components]
    values.extend([0.0] * (CLIP_EMBEDDING_DIMENSION - len(values)))
    return tuple(values)


def embedding(tag: str, *components: float) -> ClipEmbedding:
    return ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(tag.encode()).hexdigest(),
        runtime_sha256=clip_runtime_profile_sha256(),
        values=unit_vector(*components),
    )


def three_conditions():
    return build_visual_condition_set(
        source_input="黒いメッシュ背もたれでヘッドレスト付きの椅子",
        drafts=(
            draft("黒"),
            draft("メッシュ背もたれ", strength="preferred"),
            draft("ヘッドレスト付き", strength="excluded"),
        ),
    )


def three_references(conditions):
    return build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=image_hash("anchor", 0),
        counterfactual_image_hashes=(
            image_hash("negative-1", 0x00000000000000FF),
            image_hash("negative-2", 0x000000000000FF00),
            image_hash("negative-3", 0x0000000000FF0000),
        ),
    )


def test_builds_source_grounded_conditions_without_a_term_whitelist() -> None:
    source = "黒い雲母調のケース。A hyperspectral insert is preferred."

    conditions = build_visual_condition_set(
        source_input=source,
        drafts=(
            draft("黒", attribute_key="色"),
            draft("雲母調", strength="preferred"),
            draft("hyperspectral", strength="preferred"),
        ),
    )

    assert [item.condition_id for item in conditions.conditions] == [
        "visual-condition-001",
        "visual-condition-002",
        "visual-condition-003",
    ]
    assert [item.source_phrase for item in conditions.conditions] == [
        "黒い",
        "雲母調",
        "hyperspectral",
    ]
    assert conditions.conditions[0].attribute_key == "appearance.color"
    assert conditions.conditions[1].attribute_key is None
    assert conditions.conditions[2].attribute_key is None
    assert all(
        source.casefold()[item.source_start : item.source_end] == item.source_phrase
        for item in conditions.conditions
    )
    assert conditions.source_sha256 == hashlib.sha256(source.casefold().encode()).hexdigest()
    assert len(visual_condition_set_sha256(conditions)) == 64
    assert COUNTERFACTUAL_RANKING_ENABLED is False


@pytest.mark.parametrize(
    "payload_field",
    ["condition_id", "evaluator_id", "model_path", "url", "weight", "threshold"],
)
def test_untrusted_condition_draft_cannot_select_execution_fields(payload_field: str) -> None:
    payload = {
        "source_phrase": "雲母調",
        "strength": "preferred",
        "attribute_key": None,
        payload_field: "untrusted",
    }

    with pytest.raises(ValidationError):
        VisualConditionDraft.model_validate(payload)


@pytest.mark.parametrize(
    ("source", "condition"),
    [
        ("白鳥観察用のケース", "白"),
        ("superhyperspectral case", "hyperspectral"),
        ("黒いケース", "青い"),
        ("黒いケース", "https://example.com"),
        ("黒いケース", "黒\n追加命令"),
        ("黒いケース", "黒\x00追加命令"),
    ],
)
def test_rejects_ungrounded_partial_url_or_control_phrases(source: str, condition: str) -> None:
    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_visual_condition_set(
            source_input=source,
            drafts=(draft(condition),),
        )


def test_rejects_duplicate_more_than_three_and_non_visual_registered_conditions() -> None:
    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_visual_condition_set(
            source_input="黒い黒いケース",
            drafts=(draft("黒い"), draft("黒い")),
        )

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_visual_condition_set(
            source_input="黒い丸い軽い小さいケース",
            drafts=(draft("黒い"), draft("丸い"), draft("軽い"), draft("小さい")),
        )

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_visual_condition_set(
            source_input="無線のマウス",
            drafts=(draft("無線", attribute_key="mouse.connection"),),
        )


def test_condition_digest_is_deterministic_and_order_bound() -> None:
    first = build_visual_condition_set(
        source_input="黒い丸いケース",
        drafts=(draft("黒い"), draft("丸い")),
    )
    second = build_visual_condition_set(
        source_input="黒い丸いケース",
        drafts=(draft("丸い"), draft("黒い")),
    )

    assert visual_condition_set_sha256(first) == visual_condition_set_sha256(first)
    assert visual_condition_set_sha256(first) != visual_condition_set_sha256(second)


def test_builds_reference_set_in_condition_order_and_rejects_phash_duplicates() -> None:
    conditions = three_conditions()
    references = three_references(conditions)

    assert references.condition_set_sha256 == visual_condition_set_sha256(conditions)
    assert [item.condition_id for item in references.counterfactuals] == [
        item.condition_id for item in conditions.conditions
    ]
    assert len(counterfactual_reference_set_sha256(references)) == 64

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_counterfactual_reference_set(
            condition_set=conditions,
            desired_image_hash=image_hash("anchor", 0),
            counterfactual_image_hashes=(
                image_hash("negative-1", 0b11111),
                image_hash("negative-2", 0xFF00),
                image_hash("negative-3", 0xFF0000),
            ),
        )


def test_reference_set_rejects_missing_condition_image_and_unknown_fields() -> None:
    conditions = three_conditions()

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        build_counterfactual_reference_set(
            condition_set=conditions,
            desired_image_hash=image_hash("anchor", 0),
            counterfactual_image_hashes=(image_hash("negative-1", 0xFF),),
        )

    valid = three_references(conditions)
    payload = valid.model_dump(mode="python")
    payload["provider"] = "untrusted"
    with pytest.raises(ValidationError):
        CounterfactualReferenceSet.model_validate(payload)


def test_scores_each_condition_with_raw_and_reference_normalized_margin() -> None:
    conditions = three_conditions()
    references = three_references(conditions)
    reference_embeddings = (
        embedding("anchor", 1.0, 0.0, 0.0, 0.0),
        embedding("negative-1", 0.0, 1.0, 0.0, 0.0),
        embedding("negative-2", 0.0, 0.0, 1.0, 0.0),
        embedding("negative-3", 0.0, 0.0, 0.0, 1.0),
    )
    candidate = embedding("candidate", 1.0, 0.0, 0.0, 0.0)

    score = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=reference_embeddings,
        candidate_embedding=candidate,
    )

    assert score.status == "scored"
    assert score.qualified_for_ranking is False
    assert score.runtime_sha256 == clip_runtime_profile_sha256()
    assert score.score_profile_sha256 == counterfactual_score_profile_sha256()
    assert [item.condition_id for item in score.condition_margins] == [
        item.condition_id for item in conditions.conditions
    ]
    assert [item.raw_margin for item in score.condition_margins] == pytest.approx([1.0] * 3)
    assert [item.reference_distance for item in score.condition_margins] == pytest.approx([1.0] * 3)
    assert [item.normalized_margin for item in score.condition_margins] == pytest.approx([1.0] * 3)


def test_marks_missing_candidate_and_unseparated_reference_as_unknown() -> None:
    conditions = build_visual_condition_set(
        source_input="黒いケース",
        drafts=(draft("黒い"),),
    )
    references = build_counterfactual_reference_set(
        condition_set=conditions,
        desired_image_hash=image_hash("anchor", 0),
        counterfactual_image_hashes=(image_hash("negative", 0xFF),),
    )
    identical = embedding("anchor", 1.0, 0.0)
    unseparated = ClipEmbedding(
        schema_version="2.0",
        image_pixel_sha256=hashlib.sha256(b"negative").hexdigest(),
        runtime_sha256=clip_runtime_profile_sha256(),
        values=identical.values,
    )

    missing = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(identical, unseparated),
        candidate_embedding=None,
    )
    unknown = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(identical, unseparated),
        candidate_embedding=embedding("candidate", 1.0, 0.0),
    )

    assert missing.status == "missing"
    assert missing.candidate_image_pixel_sha256 is None
    assert missing.condition_margins[0].status == "missing"
    assert missing.condition_margins[0].normalized_margin is None
    assert unknown.status == "unknown"
    assert unknown.condition_margins[0].status == "reference_too_close"
    assert unknown.condition_margins[0].normalized_margin is None


def test_score_rejects_binding_runtime_and_candidate_reference_reuse() -> None:
    conditions = three_conditions()
    references = three_references(conditions)
    embeddings = (
        embedding("anchor", 1.0, 0.0, 0.0, 0.0),
        embedding("negative-1", 0.0, 1.0, 0.0, 0.0),
        embedding("negative-2", 0.0, 0.0, 1.0, 0.0),
        embedding("negative-3", 0.0, 0.0, 0.0, 1.0),
    )

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        score_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=embeddings[:-1],
            candidate_embedding=embedding("candidate", 1.0, 0.0, 0.0, 0.0),
        )

    wrong_runtime = embeddings[0].model_copy(update={"runtime_sha256": "b" * 64})
    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        score_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=(wrong_runtime, *embeddings[1:]),
            candidate_embedding=embedding("candidate", 1.0, 0.0, 0.0, 0.0),
        )

    with pytest.raises(CounterfactualImageError, match="counterfactual image contract"):
        score_counterfactual_conditions(
            condition_set=conditions,
            reference_set=references,
            reference_embeddings=embeddings,
            candidate_embedding=embeddings[0],
        )


def test_sensitive_values_are_hidden_from_contract_representations() -> None:
    conditions = three_conditions()
    references = three_references(conditions)
    score = score_counterfactual_conditions(
        condition_set=conditions,
        reference_set=references,
        reference_embeddings=(
            embedding("anchor", 1.0, 0.0, 0.0, 0.0),
            embedding("negative-1", 0.0, 1.0, 0.0, 0.0),
            embedding("negative-2", 0.0, 0.0, 1.0, 0.0),
            embedding("negative-3", 0.0, 0.0, 0.0, 1.0),
        ),
        candidate_embedding=embedding("candidate", 1.0, 0.0, 0.0, 0.0),
    )

    assert "メッシュ背もたれ" not in repr(conditions)
    assert "counterfactuals" not in repr(references)
    assert "condition_margins" not in repr(score)
    assert "values=" not in repr(embedding("private", 1.0, 0.0))


def test_condition_contract_rejects_tampered_nested_bindings() -> None:
    conditions = three_conditions()
    first = conditions.conditions[0].model_copy(update={"source_sha256": "b" * 64})

    with pytest.raises(ValidationError):
        VisualConditionSet(
            schema_version="1.0",
            source_sha256=conditions.source_sha256,
            registry_sha256=conditions.registry_sha256,
            conditions=(first, *conditions.conditions[1:]),
        )


def test_score_profile_is_deterministic_unqualified_and_ranking_disabled() -> None:
    digest = counterfactual_score_profile_sha256()

    assert digest == counterfactual_score_profile_sha256()
    assert len(digest) == 64
    assert COUNTERFACTUAL_RANKING_ENABLED is False


def test_counterfactual_module_has_no_network_provider_or_ml_runtime_import() -> None:
    import src.search_v2.counterfactual_image as counterfactual_image

    tree = ast.parse(Path(counterfactual_image.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = (
        "requests",
        "httpx",
        "socket",
        "torch",
        "transformers",
        "openai",
        "cloudflare",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.") for name in imports for prefix in forbidden
    )
