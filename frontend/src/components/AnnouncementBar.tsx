import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { useRestaurant } from "@/contexts/RestaurantContext";

export function AnnouncementBar() {
  const { announcement, announcementActive } = useRestaurant();
  const text = announcement.trim();
  const isActive = announcementActive === "true" && text.length > 0;
  const [dismissed, setDismissed] = useState(false);

  const storageKey = useMemo(
    () => `announcement_bar_dismissed:${text}`,
    [text],
  );

  useEffect(() => {
    if (!isActive) {
      setDismissed(false);
      return;
    }
    try {
      setDismissed(sessionStorage.getItem(storageKey) === "1");
    } catch {
      setDismissed(false);
    }
  }, [isActive, storageKey]);

  const close = () => {
    try {
      sessionStorage.setItem(storageKey, "1");
    } catch {
      // Ignore storage failures in private browsing modes.
    }
    setDismissed(true);
  };

  if (!isActive || dismissed) return null;

  return (
    <div
      className="w-full text-white"
      style={{ backgroundColor: "var(--brand-primary)" }}
    >
      <div className="relative mx-auto max-w-7xl px-4 py-2 lg:px-8">
        <p className="px-8 text-center text-sm font-medium">{text}</p>
        <button
          type="button"
          onClick={close}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-white/90 transition-colors hover:bg-white/15 hover:text-white"
          aria-label="Dismiss announcement"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
