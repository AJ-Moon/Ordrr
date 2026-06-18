import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

export function ServiceStatusBanner() {
  const [status, setStatus] = useState<"ok" | "down">("ok");

  useEffect(() => {
    const onDown = () => setStatus("down");
    const onOk = () => setStatus("ok");

    window.addEventListener("api:service-unavailable", onDown);
    window.addEventListener("api:service-recovered", onOk);

    return () => {
      window.removeEventListener("api:service-unavailable", onDown);
      window.removeEventListener("api:service-recovered", onOk);
    };
  }, []);

  if (status === "ok") return null;

  return (
    <div className="sticky top-0 z-[70] border-b border-amber-300 bg-amber-50 text-amber-900">
      <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-2 text-sm lg:px-8">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          Service is temporarily unstable. Some sections may fail to load. Use
          Retry in the section that failed.
        </span>
      </div>
    </div>
  );
}
