import { useEffect, useMemo, useRef, useState } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  Flame,
  Star,
  Loader2,
  Upload,
  GripVertical,
  Info,
  Sparkles,
  FileImage,
  FileText,
  FileUp,
} from "lucide-react";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const CATEGORIES = ["burgers", "pizza", "wraps", "sides", "drinks", "desserts"];

function adminFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("admin_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

interface MenuItem {
  id: number;
  category: string;
  name: string;
  description: string;
  price: number;
  salePrice?: number | null;
  image: string;
  rating: number;
  isSpicy: boolean;
  isPopular: boolean;
  isFeatured: boolean;
  isAvailable: boolean;
  displayOrder?: number | null;
  currency: string;
  ingredientCost?: number | null;
  packagingCost: number;
}

interface ImportItemDraft {
  id: string;
  selected: boolean;
  name: string;
  description: string;
  category: string;
  price: number;
  isSpicy: boolean;
  isPopular: boolean;
}

type ImportStep = "upload" | "processing" | "review" | "saving";

const EMPTY: Omit<MenuItem, "id"> = {
  category: "burgers",
  name: "",
  description: "",
  price: 0,
  salePrice: null,
  image: "",
  rating: 1,
  isSpicy: false,
  isPopular: false,
  isFeatured: false,
  isAvailable: true,
  currency: "USD",
  ingredientCost: null,
  packagingCost: 0,
};

const categorySortOrder = new Map(CATEGORIES.map((cat, idx) => [cat, idx]));

const formatCategoryLabel = (category: string) =>
  category
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");

const sortMenuItems = (a: MenuItem, b: MenuItem) => {
  const aOrder = a.displayOrder ?? Number.MAX_SAFE_INTEGER;
  const bOrder = b.displayOrder ?? Number.MAX_SAFE_INTEGER;
  if (aOrder !== bOrder) return aOrder - bOrder;
  return a.name.localeCompare(b.name);
};

const bytesToHuman = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** i;
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
};

const parseBoolean = (value: unknown) => {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return normalized === "true" || normalized === "yes" || normalized === "1";
  }
  return false;
};

const normalizeCategory = (value: unknown) => {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (!raw) return "uncategorized";
  const cleaned = raw.replace(/[^a-z0-9\s-]/g, "");
  if (cleaned.endsWith("s") && cleaned.length > 3) {
    return cleaned.slice(0, -1);
  }
  return cleaned;
};

const fileToText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve((e.target?.result as string) ?? "");
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsText(file);
  });

interface RatingSelectorProps {
  value: number;
  onChange: (value: number) => void;
}

function RatingSelector({ value, onChange }: RatingSelectorProps) {
  const normalized = Math.max(1, Math.min(5, Math.round(value * 2) / 2));

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => {
          const fillWidth =
            normalized >= star
              ? "100%"
              : normalized >= star - 0.5
                ? "50%"
                : "0%";
          return (
            <button
              key={star}
              type="button"
              className="relative h-8 w-8"
              onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const clickOffset = event.clientX - rect.left;
                const half = clickOffset < rect.width / 2;
                onChange(Math.max(1, half ? star - 0.5 : star));
              }}
              aria-label={`Set rating to ${star} stars`}
            >
              <Star className="h-8 w-8 text-muted-foreground" />
              <div
                className="pointer-events-none absolute inset-0 overflow-hidden"
                style={{ width: fillWidth }}
              >
                <Star className="h-8 w-8 fill-amber-400 text-amber-400" />
              </div>
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Selected: {normalized.toFixed(1)} / 5.0
      </p>
    </div>
  );
}

interface SortableMenuRowProps {
  item: MenuItem;
  onEdit: (item: MenuItem) => void;
  onDelete: (id: number) => void;
}

function SortableMenuRow({ item, onEdit, onDelete }: SortableMenuRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: item.id,
  });

  return (
    <TableRow
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(isDragging && "bg-muted/70")}
    >
      <TableCell className="w-10">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 cursor-grab active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4 text-muted-foreground" />
          <span className="sr-only">Drag to reorder</span>
        </Button>
      </TableCell>
      <TableCell>
        <div className="font-medium">{item.name}</div>
        <div className="max-w-[240px] truncate text-xs text-muted-foreground">
          {item.description}
        </div>
      </TableCell>
      <TableCell>${item.price.toFixed(2)}</TableCell>
      <TableCell>
        {item.ingredientCost == null ? (
          <span className="text-xs text-amber-600">Missing</span>
        ) : (
          `${item.currency} ${(item.ingredientCost + item.packagingCost).toFixed(2)}`
        )}
      </TableCell>
      <TableCell>★ {item.rating.toFixed(1)}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {item.isSpicy && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
              <Flame className="h-3 w-3" />
              Spicy
            </span>
          )}
          {item.isPopular && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
              <Star className="h-3 w-3" />
              Popular
            </span>
          )}
          {item.isFeatured && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
              Featured
            </span>
          )}
          {!item.isAvailable && (
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700">
              Unavailable
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => onEdit(item)}
        >
          <Pencil className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={() => onDelete(item.id)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

export default function AdminMenuPage() {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [categorySuggestions, setCategorySuggestions] = useState<string[]>([]);
  const [showGuide, setShowGuide] = useState(true);
  const [openImport, setOpenImport] = useState(false);
  const [importStep, setImportStep] = useState<ImportStep>("upload");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPastedText, setImportPastedText] = useState("");
  const [importDragOver, setImportDragOver] = useState(false);
  const [importImagePreviewUrl, setImportImagePreviewUrl] = useState("");
  const [importTextPreview, setImportTextPreview] = useState("");
  const [importError, setImportError] = useState("");
  const [parsedImportItems, setParsedImportItems] = useState<ImportItemDraft[]>(
    [],
  );
  const [importCurrency, setImportCurrency] = useState("Rs.");
  const [saveProgress, setSaveProgress] = useState({ done: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [form, setForm] = useState<Omit<MenuItem, "id">>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const selectedImportCount = useMemo(
    () => parsedImportItems.filter((item) => item.selected).length,
    [parsedImportItems],
  );

  const fetchItems = async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/menu");
      if (res.ok) setItems(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  useEffect(() => {
    const dismissed =
      localStorage.getItem("admin_menu_guide_dismissed") === "true";
    if (dismissed) setShowGuide(false);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/menu/categories", { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: unknown) => {
        const next = Array.isArray(data)
          ? Array.from(
              new Set(
                data
                  .map((value) =>
                    typeof value === "string" ? value.trim() : "",
                  )
                  .filter(Boolean),
              ),
            )
          : [];
        setCategorySuggestions(next);
      })
      .catch(() => undefined);

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!importFile || !importFile.type.startsWith("image/")) {
      setImportImagePreviewUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(importFile);
    setImportImagePreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [importFile]);

  useEffect(() => {
    if (!importFile || importFile.type !== "text/plain") {
      setImportTextPreview("");
      return;
    }

    let canceled = false;
    fileToText(importFile)
      .then((text) => {
        if (!canceled) setImportTextPreview(text.slice(0, 1200));
      })
      .catch(() => {
        if (!canceled) setImportTextPreview("");
      });

    return () => {
      canceled = true;
    };
  }, [importFile]);

  const resetImportFlow = () => {
    setImportStep("upload");
    setImportFile(null);
    setImportPastedText("");
    setImportDragOver(false);
    setImportImagePreviewUrl("");
    setImportTextPreview("");
    setImportError("");
    setParsedImportItems([]);
    setSaveProgress({ done: 0, total: 0 });
    if (importFileInputRef.current) {
      importFileInputRef.current.value = "";
    }
  };

  const closeImportModal = () => {
    setOpenImport(false);
    resetImportFlow();
  };

  const openImportModal = () => {
    resetImportFlow();
    setOpenImport(true);
  };

  const onImportFilePicked = (file?: File) => {
    if (!file) return;
    const allowed = [
      "image/jpeg",
      "image/png",
      "application/pdf",
      "text/plain",
    ];
    if (!allowed.includes(file.type)) {
      toast.error("Supported types: JPG, PNG, PDF, TXT");
      return;
    }
    setImportError("");
    setImportFile(file);
  };

  const onImportDrop: React.DragEventHandler<HTMLDivElement> = (event) => {
    event.preventDefault();
    setImportDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onImportFilePicked(file);
  };

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY);
    setOpen(true);
  };
  const openEdit = (item: MenuItem) => {
    setEditing(item);
    setForm({
      ...item,
      salePrice: item.salePrice ?? null,
      isFeatured: item.isFeatured ?? false,
      isAvailable: item.isAvailable ?? true,
    });
    setOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const url = editing ? `/api/admin/menu/${editing.id}` : "/api/admin/menu";
      const method = editing ? "PATCH" : "POST";
      let res = await adminFetch(url, { method, body: JSON.stringify(form) });
      // Retry once on transient server/DB errors (Supabase cold-start drops)
      if (res.status >= 500) {
        await new Promise((r) => setTimeout(r, 600));
        res = await adminFetch(url, { method, body: JSON.stringify(form) });
      }
      if (res.ok) {
        const saved = await res.json();
        setItems((prev) =>
          editing
            ? prev.map((i) => (i.id === editing.id ? saved : i))
            : [...prev, saved],
        );
        toast.success(editing ? "Item updated" : "Item added");
        setOpen(false);
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(
          err?.detail ??
            `Failed to save item (${res.status}). Please try again.`,
        );
      }
    } catch {
      toast.error(
        "Network error — please check your connection and try again.",
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this menu item?")) return;
    await adminFetch(`/api/admin/menu/${id}`, { method: "DELETE" });
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  const set = <K extends keyof typeof form>(key: K, val: (typeof form)[K]) =>
    setForm((prev) => ({ ...prev, [key]: val }));

  const uploadImage = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      toast.error("Please select an image file");
      return;
    }

    const token = localStorage.getItem("admin_token");
    const formData = new FormData();
    formData.append("file", file);

    setIsUploadingImage(true);
    try {
      const res = await fetch("/api/admin/upload-image", {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data: { url?: string } = await res.json();
      if (!data.url) throw new Error("Invalid upload response");

      set("image", data.url);
      toast.success("Image uploaded");
    } catch {
      toast.error("Failed to upload image");
    } finally {
      setIsUploadingImage(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const onDropImage: React.DragEventHandler<HTMLDivElement> = async (event) => {
    event.preventDefault();
    setIsDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      await uploadImage(file);
    }
  };

  const runMenuParse = async () => {
    setImportError("");
    setImportStep("processing");

    try {
      const file = importFile;
      const pasted = importPastedText.trim();

      if (!file && !pasted) {
        throw new Error("Upload a file or paste menu text first.");
      }

      const token = localStorage.getItem("admin_token");
      const formData = new FormData();
      if (file) formData.append("file", file);
      if (pasted) formData.append("text", pasted);

      const res = await fetch("/api/admin/parse-menu", {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(
          err?.detail ||
            "Could not parse this menu. Try a clearer image or paste the text manually.",
        );
      }

      const data = (await res.json()) as {
        items: Array<Record<string, unknown>>;
      };
      const normalized: ImportItemDraft[] = data.items.map((item, index) => ({
        id:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `${Date.now()}-${index}`,
        selected: true,
        name: String(item.name ?? "").trim(),
        description: String(item.description ?? "").trim(),
        category: normalizeCategory(item.category),
        price: Math.max(0, Number(item.price) || 0),
        isSpicy: parseBoolean(item.isSpicy),
        isPopular: parseBoolean(item.isPopular),
      }));

      if (normalized.length === 0) {
        throw new Error(
          "No menu items found. Try a clearer image or paste the text manually.",
        );
      }

      setParsedImportItems(normalized);
      setImportStep("review");
    } catch (error) {
      setImportStep("upload");
      setImportError(
        error instanceof Error
          ? error.message
          : "Could not parse this menu. Try a clearer image or paste the text manually.",
      );
    }
  };

  const setImportItem = <K extends keyof ImportItemDraft>(
    id: string,
    key: K,
    value: ImportItemDraft[K],
  ) => {
    setParsedImportItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [key]: value } : item)),
    );
  };

  const toggleAllImportItems = (checked: boolean) => {
    setParsedImportItems((prev) =>
      prev.map((item) => ({ ...item, selected: checked })),
    );
  };

  const importSelectedItems = async () => {
    const selected = parsedImportItems.filter((item) => item.selected);
    if (selected.length === 0) {
      toast.error("Select at least one item to import");
      return;
    }

    setImportStep("saving");
    setSaveProgress({ done: 0, total: selected.length });

    let success = 0;
    let failed = 0;

    for (let i = 0; i < selected.length; i += 1) {
      const item = selected[i];
      try {
        const res = await adminFetch("/api/admin/menu", {
          method: "POST",
          body: JSON.stringify({
            category: normalizeCategory(item.category),
            name: item.name.trim(),
            description: item.description.trim(),
            price: Math.max(0, Number(item.price) || 0),
            salePrice: null,
            currency: "USD",
            ingredientCost: null,
            packagingCost: 0,
            image: "",
            rating: 1,
            isSpicy: item.isSpicy,
            isPopular: item.isPopular,
            isFeatured: false,
            isAvailable: true,
          }),
        });
        if (!res.ok) throw new Error("failed");
        success += 1;
      } catch {
        failed += 1;
      } finally {
        setSaveProgress({ done: i + 1, total: selected.length });
      }
    }

    if (success > 0) {
      await fetchItems();
    }

    if (failed === 0) {
      toast.success(`Imported ${success} menu items`);
      closeImportModal();
      return;
    }

    setImportStep("review");
    toast.error(`Imported ${success} items, ${failed} failed. Please retry.`);
  };

  const groupedItems = useMemo(() => {
    const groups = new Map<string, MenuItem[]>();
    for (const item of items) {
      const existing = groups.get(item.category);
      if (existing) existing.push(item);
      else groups.set(item.category, [item]);
    }

    const entries = Array.from(groups.entries()).map(
      ([category, grouped]) =>
        [category, [...grouped].sort(sortMenuItems)] as const,
    );

    entries.sort((a, b) => {
      const aOrder = categorySortOrder.get(a[0]) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = categorySortOrder.get(b[0]) ?? Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a[0].localeCompare(b[0]);
    });

    return entries;
  }, [items]);

  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const activeId = Number(active.id);
    const overId = Number(over.id);
    const activeItem = items.find((item) => item.id === activeId);
    const overItem = items.find((item) => item.id === overId);

    if (!activeItem || !overItem || activeItem.category !== overItem.category)
      return;

    const categoryItems = items
      .filter((item) => item.category === activeItem.category)
      .sort(sortMenuItems);
    const oldIndex = categoryItems.findIndex((item) => item.id === activeId);
    const newIndex = categoryItems.findIndex((item) => item.id === overId);

    if (oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) return;

    const reordered = arrayMove(categoryItems, oldIndex, newIndex);
    const orderedIds = reordered.map((item) => item.id);

    setItems((prev) => {
      const indexById = new Map<number, number>(
        orderedIds.map((id, idx) => [id, idx + 1]),
      );
      return prev.map((item) =>
        item.category === activeItem.category && indexById.has(item.id)
          ? {
              ...item,
              displayOrder: indexById.get(item.id) ?? item.displayOrder,
            }
          : item,
      );
    });

    try {
      const res = await adminFetch("/api/admin/menu/reorder", {
        method: "PATCH",
        body: JSON.stringify({ ordered_ids: orderedIds }),
      });
      if (!res.ok) throw new Error("Failed to save order");
    } catch {
      toast.error("Failed to save new item order");
      fetchItems();
    }
  };

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Menu</h1>
          <p className="text-sm text-muted-foreground">{items.length} items</p>
        </div>
        <div className="flex items-center gap-2">
          {!showGuide && (
            <Button
              variant="outline"
              onClick={() => {
                localStorage.removeItem("admin_menu_guide_dismissed");
                setShowGuide(true);
              }}
            >
              Show Setup Guide
            </Button>
          )}
          <Button variant="outline" onClick={openImportModal}>
            <Sparkles className="mr-2 h-4 w-4" /> Import Menu with AI
          </Button>
          <Button onClick={openAdd}>
            <Plus className="mr-2 h-4 w-4" /> Add Item
          </Button>
        </div>
      </div>

      {showGuide && (
        <div className="mb-6 rounded-xl border bg-muted/30 p-4">
          <div className="mb-3 flex items-start justify-between gap-4">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <h2 className="text-sm font-semibold">Quick Setup Guide</h2>
                <p className="text-xs text-muted-foreground">
                  Follow these steps to avoid missing a category, item detail,
                  or display order.
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                localStorage.setItem("admin_menu_guide_dismissed", "true");
                setShowGuide(false);
              }}
            >
              Dismiss
            </Button>
          </div>
          <ol className="ml-5 list-decimal space-y-1 text-sm text-foreground">
            <li>
              Create or pick a category in the Category field. Existing
              categories appear as suggestions.
            </li>
            <li>
              Upload an image and confirm the preview before saving the item.
            </li>
            <li>
              Set price, optional sale price, rating, tags, and availability.
            </li>
            <li>
              Repeat for each category to complete your full menu structure.
            </li>
            <li>
              Drag items within a category to control customer-facing display
              order.
            </li>
          </ol>
        </div>
      )}

      <div className="rounded-xl border bg-card">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Name</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Food Cost</TableHead>
                <TableHead>Rating</TableHead>
                <TableHead>Tags</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Skeleton className="h-5 w-6" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-36" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-14" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-14" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-10" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-16" />
                      </TableCell>
                      <TableCell className="text-right">
                        <Skeleton className="ml-auto h-8 w-16" />
                      </TableCell>
                    </TableRow>
                  ))
                : groupedItems.flatMap(([category, categoryItems]) => [
                    <TableRow
                      key={`heading-${category}`}
                      className="bg-muted/40 hover:bg-muted/40"
                    >
                      <TableCell colSpan={7} className="font-semibold">
                        {formatCategoryLabel(category)} ({categoryItems.length})
                      </TableCell>
                    </TableRow>,
                    <SortableContext
                      key={`sortable-${category}`}
                      items={categoryItems.map((item) => item.id)}
                      strategy={verticalListSortingStrategy}
                    >
                      {categoryItems.map((item) => (
                        <SortableMenuRow
                          key={item.id}
                          item={item}
                          onEdit={openEdit}
                          onDelete={remove}
                        />
                      ))}
                    </SortableContext>,
                  ])}
              {!loading && groupedItems.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-6 text-center text-sm text-muted-foreground"
                  >
                    No menu items yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </DndContext>
      </div>

      <Dialog
        open={openImport}
        onOpenChange={(next) =>
          next ? setOpenImport(true) : closeImportModal()
        }
      >
        <DialogContent
          className="max-w-4xl w-[95vw]"
          aria-describedby={undefined}
        >
          <DialogHeader>
            <DialogTitle>Import Menu with AI</DialogTitle>
          </DialogHeader>

          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span
              className={cn(
                "rounded-full border px-2 py-1",
                importStep === "upload" && "border-primary text-primary",
              )}
            >
              1. Upload
            </span>
            <span
              className={cn(
                "rounded-full border px-2 py-1",
                importStep === "processing" && "border-primary text-primary",
              )}
            >
              2. Processing
            </span>
            <span
              className={cn(
                "rounded-full border px-2 py-1",
                importStep === "review" && "border-primary text-primary",
              )}
            >
              3. Review
            </span>
            <span
              className={cn(
                "rounded-full border px-2 py-1",
                importStep === "saving" && "border-primary text-primary",
              )}
            >
              4. Save
            </span>
          </div>

          {importStep === "upload" && (
            <div className="space-y-4 py-1">
              <input
                ref={importFileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.pdf,.txt"
                className="hidden"
                onChange={(event) =>
                  onImportFilePicked(event.target.files?.[0])
                }
              />

              <div
                role="button"
                tabIndex={0}
                onClick={() => importFileInputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    importFileInputRef.current?.click();
                  }
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setImportDragOver(true);
                }}
                onDragLeave={() => setImportDragOver(false)}
                onDrop={onImportDrop}
                className={cn(
                  "w-full rounded-xl border-2 border-dashed p-8 text-center transition-colors",
                  importDragOver
                    ? "border-primary bg-primary/5"
                    : "border-border",
                )}
              >
                <FileUp className="mx-auto h-7 w-7 text-muted-foreground" />
                <p className="mt-3 text-sm font-medium">
                  Drop your menu file here, or click to browse
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Accepted types: JPG, PNG, PDF, TXT
                </p>
              </div>

              {(importFile || importPastedText.trim()) && (
                <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
                  {importFile && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm">
                        {importFile.type.startsWith("image/") ? (
                          <FileImage className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <FileText className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="font-medium">{importFile.name}</span>
                        <span className="text-xs text-muted-foreground">
                          ({bytesToHuman(importFile.size)})
                        </span>
                      </div>

                      {importImagePreviewUrl && (
                        <img
                          src={importImagePreviewUrl}
                          alt="Import preview"
                          className="max-h-48 rounded-md border object-contain"
                        />
                      )}

                      {importFile.type === "application/pdf" && (
                        <p className="text-xs text-muted-foreground">
                          PDF selected and ready to parse.
                        </p>
                      )}

                      {importFile.type === "text/plain" &&
                        importTextPreview && (
                          <div className="rounded-md border bg-background p-3 text-xs text-muted-foreground whitespace-pre-wrap max-h-40 overflow-auto">
                            {importTextPreview}
                          </div>
                        )}
                    </div>
                  )}

                  {importPastedText.trim() && (
                    <div className="rounded-md border bg-background p-3 text-xs text-muted-foreground whitespace-pre-wrap max-h-40 overflow-auto">
                      {importPastedText.trim()}
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="menu-import-paste">
                  Or paste text (.doc contents)
                </Label>
                <Textarea
                  id="menu-import-paste"
                  value={importPastedText}
                  onChange={(event) => setImportPastedText(event.target.value)}
                  placeholder="Paste menu text here if you copied it from a document"
                  className="min-h-28"
                />
              </div>

              {importError && (
                <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3">
                  <p className="text-sm text-destructive">{importError}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={runMenuParse}
                    disabled={!importFile && !importPastedText.trim()}
                  >
                    Retry
                  </Button>
                </div>
              )}
            </div>
          )}

          {importStep === "processing" && (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 py-8">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm font-medium">Reading your menu...</p>
            </div>
          )}

          {importStep === "review" && (
            <div className="space-y-4 py-1">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {parsedImportItems.length} items found - {selectedImportCount}{" "}
                  selected
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Currency:
                  </span>
                  <select
                    value={importCurrency}
                    onChange={(e) => setImportCurrency(e.target.value)}
                    className="h-7 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="Rs.">Rs. — Pakistani Rupee</option>
                    <option value="$">$ — US Dollar</option>
                    <option value="AED">AED — Dirham</option>
                    <option value="SAR">SAR — Saudi Riyal</option>
                    <option value="£">£ — British Pound</option>
                    <option value="€">€ — Euro</option>
                  </select>
                </div>
              </div>

              <div className="max-h-[420px] overflow-auto rounded-lg border">
                <Table className="table-fixed w-full">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8">
                        <Checkbox
                          checked={
                            parsedImportItems.length > 0 &&
                            selectedImportCount === parsedImportItems.length
                          }
                          onCheckedChange={(checked) =>
                            toggleAllImportItems(Boolean(checked))
                          }
                        />
                      </TableHead>
                      <TableHead className="w-[170px]">Name</TableHead>
                      <TableHead className="w-[110px]">Category</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="w-32">Price</TableHead>
                      <TableHead className="w-12 text-center">Spicy</TableHead>
                      <TableHead className="w-14 text-center">
                        Popular
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {parsedImportItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Checkbox
                            checked={item.selected}
                            onCheckedChange={(value) =>
                              setImportItem(item.id, "selected", Boolean(value))
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={item.name}
                            className="w-full"
                            onChange={(event) =>
                              setImportItem(item.id, "name", event.target.value)
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={item.category}
                            className="w-full"
                            onChange={(event) =>
                              setImportItem(
                                item.id,
                                "category",
                                event.target.value,
                              )
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={item.description}
                            className="w-full"
                            onChange={(event) =>
                              setImportItem(
                                item.id,
                                "description",
                                event.target.value,
                              )
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center rounded-md border focus-within:ring-2 focus-within:ring-ring overflow-hidden">
                            <span className="px-2 text-xs text-muted-foreground bg-muted border-r select-none">
                              {importCurrency}
                            </span>
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={item.price}
                              className="w-full px-2 py-1.5 text-sm bg-background outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                              onChange={(event) =>
                                setImportItem(
                                  item.id,
                                  "price",
                                  Math.max(
                                    0,
                                    Number.parseFloat(event.target.value) || 0,
                                  ),
                                )
                              }
                            />
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <Checkbox
                            checked={item.isSpicy}
                            onCheckedChange={(value) =>
                              setImportItem(item.id, "isSpicy", Boolean(value))
                            }
                          />
                        </TableCell>
                        <TableCell className="text-center">
                          <Checkbox
                            checked={item.isPopular}
                            onCheckedChange={(value) =>
                              setImportItem(
                                item.id,
                                "isPopular",
                                Boolean(value),
                              )
                            }
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <p className="text-xs text-muted-foreground">
                Add a photo later after importing items.
              </p>
            </div>
          )}

          {importStep === "saving" && (
            <div className="space-y-4 py-4">
              <p className="text-sm text-muted-foreground">
                Saving items... {saveProgress.done}/{saveProgress.total}
              </p>
              <Progress
                value={
                  saveProgress.total > 0
                    ? (saveProgress.done / saveProgress.total) * 100
                    : 0
                }
              />
            </div>
          )}

          <DialogFooter>
            {importStep !== "saving" && (
              <Button variant="outline" onClick={closeImportModal}>
                Cancel
              </Button>
            )}

            {importStep === "upload" && (
              <Button
                onClick={runMenuParse}
                disabled={!importFile && !importPastedText.trim()}
              >
                Parse Menu
              </Button>
            )}

            {importStep === "review" && (
              <Button
                onClick={importSelectedItems}
                disabled={selectedImportCount === 0}
              >
                Import Selected Items
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" aria-describedby={undefined}>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Item" : "Add Menu Item"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-6 py-2 md:grid-cols-2">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Image</Label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      uploadImage(file);
                    }
                  }}
                />

                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragOver(true);
                  }}
                  onDragLeave={() => setIsDragOver(false)}
                  onDrop={onDropImage}
                  className={cn(
                    "rounded-lg border-2 border-dashed p-5 text-center transition-colors",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isDragOver
                      ? "border-primary bg-primary/5"
                      : "border-border",
                  )}
                >
                  {isUploadingImage ? (
                    <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading image...
                    </div>
                  ) : form.image ? (
                    <div className="space-y-3">
                      <img
                        src={form.image}
                        alt="Menu item preview"
                        className="mx-auto h-32 w-32 rounded-md border object-cover"
                      />
                      <p className="text-xs text-muted-foreground">
                        Click or drop a new image to replace
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Upload className="mx-auto h-5 w-5 text-muted-foreground" />
                      <p className="text-sm font-medium">
                        Drag and drop image here
                      </p>
                      <p className="text-xs text-muted-foreground">
                        or click to browse files
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="menu-category">Category</Label>
                <Input
                  id="menu-category"
                  list="menu-category-suggestions"
                  value={form.category}
                  onChange={(e) => set("category", e.target.value)}
                  placeholder="e.g. burgers"
                />
                <datalist id="menu-category-suggestions">
                  {categorySuggestions.map((category) => (
                    <option key={category} value={category} />
                  ))}
                </datalist>
              </div>

              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={form.description}
                  onChange={(e) => set("description", e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Price ($)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price}
                  onChange={(e) =>
                    set("price", parseFloat(e.target.value) || 0)
                  }
                />
              </div>

              <div className="space-y-2">
                <Label>Sale Price ($)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.salePrice ?? ""}
                  onChange={(e) => {
                    const value = e.target.value.trim();
                    set(
                      "salePrice",
                      value === "" ? null : parseFloat(value) || null,
                    );
                  }}
                  placeholder="Optional"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Ingredient Cost</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.ingredientCost ?? ""}
                    onChange={(e) => {
                      const value = e.target.value.trim();
                      set("ingredientCost", value === "" ? null : parseFloat(value) || 0);
                    }}
                    placeholder="Required for margin"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Packaging Cost</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.packagingCost}
                    onChange={(e) => set("packagingCost", parseFloat(e.target.value) || 0)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Rating</Label>
                <RatingSelector
                  value={form.rating}
                  onChange={(rating) => set("rating", rating)}
                />
              </div>

              <div className="space-y-3 rounded-md border p-3">
                <Label>Tags</Label>
                <div className="flex flex-wrap gap-4">
                  <label className="flex cursor-pointer items-center gap-2">
                    <Checkbox
                      checked={form.isSpicy}
                      onCheckedChange={(v) => set("isSpicy", !!v)}
                    />
                    <span className="text-sm">Spicy</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <Checkbox
                      checked={form.isPopular}
                      onCheckedChange={(v) => set("isPopular", !!v)}
                    />
                    <span className="text-sm">Popular</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <Checkbox
                      checked={form.isFeatured}
                      onCheckedChange={(v) => set("isFeatured", !!v)}
                    />
                    <span className="text-sm">Featured</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-md border p-3">
                <Label htmlFor="is-available">Available</Label>
                <Switch
                  id="is-available"
                  checked={form.isAvailable}
                  onCheckedChange={(v) => set("isAvailable", v)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={save}
              disabled={saving || isUploadingImage || !form.name}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
