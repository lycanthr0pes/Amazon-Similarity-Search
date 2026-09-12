import { createContext, useContext } from "react";
import { readSearch, sendSearch } from "./connected-api";
import {
  readHistoryState,
  readHistoryDetail,
  deleteHistory,
  purgeExpiredHistory,
} from "./connected-history-api";

export interface SearchClient {
  offline?: boolean;
  readSearch: typeof readSearch;
  sendSearch: typeof sendSearch;
  readHistoryState: typeof readHistoryState;
  readHistoryDetail: typeof readHistoryDetail;
  deleteHistory: typeof deleteHistory;
  purgeExpiredHistory: typeof purgeExpiredHistory;
}

export const SearchClientContext = createContext<SearchClient>({
  readSearch,
  sendSearch,
  readHistoryState,
  readHistoryDetail,
  deleteHistory,
  purgeExpiredHistory,
});
export function useSearchClient() {
  return useContext(SearchClientContext);
}
