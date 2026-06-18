import { useEffect, useMemo, useState } from "react";
import { getSessionId, getVisitorId } from "@/lib/analytics";

type Assignment = {
  assignmentId: number;
  variantId: number;
  variantKey: string;
  config: { text?: string };
};

export function ExperimentText({ placement, fallback, className }: { placement: string; fallback: string; className?: string }) {
  const [experimentId, setExperimentId] = useState<number | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const visitorId = useMemo(() => getVisitorId(), []);
  const sessionId = useMemo(() => getSessionId(), []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/experiment-assignments/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitorId, placement, audience: { path: window.location.pathname } }),
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : null)
      .then((result) => {
        if (result?.assigned && result.assignment) {
          setExperimentId(result.experimentId);
          setAssignment(result.assignment);
        }
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [placement, visitorId]);

  useEffect(() => {
    if (!experimentId || !assignment) return;
    const exposureKey = `web:${experimentId}:${sessionId}:${placement}`;
    void fetch(`/api/v1/experiments/${experimentId}/exposure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        assignmentId: assignment.assignmentId,
        variantId: assignment.variantId,
        visitorId,
        sessionId,
        exposureKey,
        context: { placement, renderedText: assignment.config.text || fallback },
      }),
    });
  }, [assignment, experimentId, fallback, placement, sessionId, visitorId]);

  return <span className={className}>{assignment?.config.text || fallback}</span>;
}
