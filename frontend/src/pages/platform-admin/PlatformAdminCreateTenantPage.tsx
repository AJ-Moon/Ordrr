import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Loader2, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

function pFetch(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("platform_admin_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

// Slug validator: lowercase letters, numbers, hyphens only
function toSlug(val: string) {
  return val
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-");
}

// Defined OUTSIDE the parent component so it is never recreated on re-render
function Field({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  error,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  error?: string;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-slate-300">
        {label}
      </Label>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-violet-500 ${
          error ? "border-red-500" : ""
        }`}
      />
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

export default function PlatformAdminCreateTenantPage() {
  const navigate = useNavigate();

  // Restaurant fields
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugManual, setSlugManual] = useState(false);
  const [primaryDomain, setPrimaryDomain] = useState("");

  // Admin account fields
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleNameChange = (val: string) => {
    setName(val);
    if (!slugManual) setSlug(toSlug(val));
  };

  const handleSlugChange = (val: string) => {
    setSlugManual(true);
    setSlug(toSlug(val));
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Restaurant name is required";
    if (!slug.trim()) e.slug = "Slug is required";
    if (!/^[a-z0-9-]+$/.test(slug))
      e.slug = "Slug can only contain lowercase letters, numbers, and hyphens";
    if (!adminEmail.trim()) e.adminEmail = "Admin email is required";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(adminEmail))
      e.adminEmail = "Enter a valid email address";
    if (!adminPassword) e.adminPassword = "Admin password is required";
    if (adminPassword.length < 8)
      e.adminPassword = "Password must be at least 8 characters";
    if (!adminName.trim()) e.adminName = "Admin name is required";
    if (
      primaryDomain &&
      !/^[a-z0-9.-]+\.[a-z]{2,}$/.test(primaryDomain.toLowerCase())
    )
      e.primaryDomain = "Enter a valid domain (e.g. myrestaurant.com)";
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setIsSubmitting(true);
    try {
      const res = await pFetch("/api/platform-admin/tenants", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          slug: slug.trim(),
          primary_domain: primaryDomain.trim() || null,
          admin_email: adminEmail.trim(),
          admin_password: adminPassword,
          admin_name: adminName.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.detail || "Failed to create tenant");
        return;
      }
      toast.success(`Tenant "${name}" created successfully!`);
      navigate(`/platform-admin/tenants/${data.restaurantId}`);
    } catch {
      toast.error("Network error. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/platform-admin/tenants">
          <Button
            variant="ghost"
            size="icon"
            className="text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">New Tenant</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Create a new restaurant on the platform
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Restaurant info */}
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-4">
            <CardTitle className="text-white text-base">
              Restaurant Information
            </CardTitle>
            <CardDescription className="text-slate-400">
              Basic details for the new tenant
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              id="name"
              label="Restaurant Name"
              value={name}
              onChange={handleNameChange}
              placeholder="Burger Palace"
              error={errors.name}
            />
            <Field
              id="slug"
              label="Slug (URL identifier)"
              value={slug}
              onChange={handleSlugChange}
              placeholder="burger-palace"
              hint="Used internally. Only lowercase letters, numbers, hyphens."
              error={errors.slug}
            />
            <Field
              id="primaryDomain"
              label="Primary Domain (optional)"
              value={primaryDomain}
              onChange={setPrimaryDomain}
              placeholder="burgerpalace.com"
              hint="The production domain for this restaurant. Can be added later."
              error={errors.primaryDomain}
            />
          </CardContent>
        </Card>

        <Separator className="bg-slate-800" />

        {/* Admin account */}
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-4">
            <CardTitle className="text-white text-base">
              Admin Account
            </CardTitle>
            <CardDescription className="text-slate-400">
              The restaurant admin who will manage this tenant via /admin
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              id="adminName"
              label="Admin Name"
              value={adminName}
              onChange={setAdminName}
              placeholder="John Smith"
              error={errors.adminName}
            />
            <Field
              id="adminEmail"
              label="Admin Email"
              value={adminEmail}
              onChange={setAdminEmail}
              placeholder="john@burgerpalace.com"
              type="email"
              error={errors.adminEmail}
            />
            <div className="space-y-1.5">
              <Label htmlFor="adminPassword" className="text-slate-300">
                Admin Password
              </Label>
              <div className="relative">
                <Input
                  id="adminPassword"
                  type={showPassword ? "text" : "password"}
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className={`bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-violet-500 pr-10 ${errors.adminPassword ? "border-red-500" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.adminPassword && (
                <p className="text-xs text-red-400">{errors.adminPassword}</p>
              )}
              {/* Password strength indicator */}
              {adminPassword.length > 0 && (
                <div className="mt-1 space-y-1">
                  {[
                    {
                      label: "At least 8 characters",
                      met: adminPassword.length >= 8,
                    },
                    {
                      label: "Contains a number",
                      met: /\d/.test(adminPassword),
                    },
                    {
                      label: "Contains a letter",
                      met: /[a-zA-Z]/.test(adminPassword),
                    },
                  ].map((r) => (
                    <div
                      key={r.label}
                      className="flex items-center gap-1.5 text-xs"
                    >
                      <CheckCircle2
                        className={`h-3 w-3 ${r.met ? "text-emerald-400" : "text-slate-600"}`}
                      />
                      <span
                        className={r.met ? "text-slate-400" : "text-slate-600"}
                      >
                        {r.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex items-center gap-3">
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-violet-600 hover:bg-violet-700 text-white"
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : null}
            {isSubmitting ? "Creating…" : "Create Tenant"}
          </Button>
          <Link to="/platform-admin/tenants">
            <Button
              type="button"
              variant="ghost"
              className="text-slate-400 hover:text-white hover:bg-slate-800"
            >
              Cancel
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
