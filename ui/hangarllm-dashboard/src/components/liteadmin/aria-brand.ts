export const ARIA_AGENT_LABEL = "DockWorker";
export const DOCKWORKER_ROUTE = "dockworker";
export const LEGACY_DOCKWORKER_ROUTE = "aria";

export const isDockWorkerRoute = (route: string): boolean =>
  route === DOCKWORKER_ROUTE || route === LEGACY_DOCKWORKER_ROUTE;
