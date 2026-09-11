"""Standalone CPU worker; no repository imports, downloads or provider credentials."""

from importlib.metadata import version
import json
from pathlib import Path
import sys


def translate(root, phrases):
    for package, expected in (
        ("ctranslate2", "4.8.2"),
        ("sentencepiece", "0.2.1"),
        ("sacremoses", "0.1.1"),
        ("numpy", "2.2.6"),
    ):
        if version(package) != expected:
            raise ValueError("Translation runtime version differs")
    import ctranslate2
    import sentencepiece
    from sacremoses import MosesPunctNormalizer

    normalizer = MosesPunctNormalizer(
        lang="ja",
        pre_replace_unicode_punct=True,
        post_remove_control_chars=True,
        perl_parity=True,
    )
    source = sentencepiece.SentencePieceProcessor(model_file=str(root / "original/source.spm"))
    target = sentencepiece.SentencePieceProcessor(model_file=str(root / "original/target.spm"))
    inputs = [
        source.encode(" ".join(normalizer.normalize(p).split()), out_type=str) for p in phrases
    ]
    if any(not tokens or len(tokens) > 512 or "<unk>" in tokens for tokens in inputs):
        raise ValueError("Unsupported translation input")
    model = ctranslate2.Translator(
        str(root / "int8_float32"),
        device="cpu",
        compute_type="int8_float32",
        inter_threads=1,
        intra_threads=2,
    )
    results = model.translate_batch(
        inputs,
        beam_size=4,
        max_decoding_length=64,
        num_hypotheses=1,
        return_end_token=True,
    )
    outputs = []
    for result in results:
        tokens = result.hypotheses[0]
        outputs.append(target.decode(tokens[:-1]) if tokens and tokens[-1] == "</s>" else None)
    return outputs


def main():
    try:
        data = sys.stdin.buffer.read(4097)
        if len(data) > 4096 or len(sys.argv) != 2:
            return 1
        phrases = json.loads(data)
        if (
            type(phrases) is not list
            or not 1 <= len(phrases) <= 2
            or any(type(p) is not str or not 0 < len(p) <= 100 for p in phrases)
        ):
            return 1
        output = json.dumps(translate(Path(sys.argv[1]), phrases), ensure_ascii=False)
        if len(output.encode()) > 16384:
            return 1
        print(output)
        return 0
    except Exception:
        return 1  # Never emit input, model output or raw exceptions on stderr.


if __name__ == "__main__":
    raise SystemExit(main())
