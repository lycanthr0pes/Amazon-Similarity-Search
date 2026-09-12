import { useState } from "react";
import ConnectedApp from "./ConnectedApp";
import { SearchClientContext } from "./search-client";
import { createOfflineClient } from "./offline-client";

export default function App() {
  const [client] = useState(() =>
    createOfflineClient(
      () => window.sessionStorage,
      new URLSearchParams(window.location.search).get("scenario") ?? "default",
    ),
  );
  return (
    <SearchClientContext.Provider value={client}>
      <ConnectedApp />
    </SearchClientContext.Provider>
  );
}
