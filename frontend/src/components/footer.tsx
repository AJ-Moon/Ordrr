import { Link } from "react-router-dom";
import React, { useEffect, useMemo, useState } from "react";
import { Instagram, Twitter, Youtube, Phone, Mail, MapPin } from "lucide-react";
import { useRestaurant } from "@/contexts/RestaurantContext";

const footerLinks = {
  company: [
    { label: "About Us", href: "/about" },
    { label: "Contact", href: "/contact" },
    { label: "Careers", href: "/careers" },
    { label: "Franchise", href: "/franchise" },
  ],
  support: [
    { label: "FAQ", href: "/faq" },
    { label: "Track Order", href: "/track" },
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
  ],
};

export function Footer() {
  const {
    restaurantName,
    primaryColor,
    footerTagline,
    instagramUrl,
    twitterUrl,
    tiktokUrl,
    whatsapp,
    phone,
    email,
    address,
  } = useRestaurant() as any;

  const [menuCategories, setMenuCategories] = useState<string[]>([]);

  useEffect(() => {
    fetch("/api/menu/categories")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: string[]) => setMenuCategories(data.slice(0, 5)))
      .catch(() => setMenuCategories([]));
  }, []);

  function formatWhatsappLink(raw: string) {
    if (!raw) return "";
    let s = String(raw).trim().replace(/\s+/g, "");
    if (s.startsWith("+")) s = s.slice(1);
    return `https://wa.me/${s}`;
  }

  const socialLinks = [
    instagramUrl ? { icon: Instagram, href: instagramUrl,               label: "Instagram" } : null,
    twitterUrl   ? { icon: Twitter,   href: twitterUrl,                 label: "Twitter"   } : null,
    tiktokUrl    ? { icon: Youtube,   href: tiktokUrl,                  label: "TikTok"    } : null,
    whatsapp     ? { icon: Phone,     href: formatWhatsappLink(whatsapp), label: "WhatsApp" } : null,
  ].filter(Boolean) as { icon: React.ElementType; href: string; label: string }[];

  const menuLinks = useMemo(
    () =>
      menuCategories.map((category) => ({
        label: category
          .replace(/[-_]+/g, " ")
          .replace(/\b\w/g, (m) => m.toUpperCase()),
        href: `/menu?category=${encodeURIComponent(category)}`,
      })),
    [menuCategories],
  );

  return (
    <>
      {/* Wave transition from dark hero to white footer */}
      <div className="bg-[#0f172a] leading-none">
        <svg
          viewBox="0 0 1440 60"
          preserveAspectRatio="none"
          className="block w-full"
          style={{ height: "60px" }}
          aria-hidden="true"
        >
          <path
            d="M0,0 C360,60 1080,60 1440,0 L1440,60 L0,60 Z"
            fill="#ffffff"
          />
        </svg>
      </div>

      <footer className="bg-white">
        <div className="mx-auto max-w-7xl px-6 pt-6 pb-8 lg:px-10">

          {/* ── Small CTA banner ── */}
          <div
            className="flex flex-col gap-3 rounded-xl p-5 sm:flex-row sm:items-center sm:justify-between mb-10"
            style={{ backgroundColor: `${primaryColor}10` }}
          >
            <div>
              <p className="text-sm font-semibold text-gray-900">
                Ready to order?
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {footerTagline || "Fresh food delivered fast."}
              </p>
            </div>
            <Link
              to="/menu"
              className="inline-flex items-center justify-center rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 whitespace-nowrap"
              style={{ backgroundColor: primaryColor }}
            >
              Order now
            </Link>
          </div>

          {/* ── Links grid ── */}
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 mb-10">

            {/* Find us */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-widest text-gray-400">
                Find us
              </h4>
              <ul className="space-y-3">
                {phone && (
                  <li>
                    <a
                      href={`tel:${phone}`}
                      className="flex items-center gap-2 text-sm text-gray-500 transition-colors hover:text-gray-900"
                    >
                      <Phone className="h-3.5 w-3.5 shrink-0" />
                      {phone}
                    </a>
                  </li>
                )}
                {email && (
                  <li>
                    <a
                      href={`mailto:${email}`}
                      className="flex items-center gap-2 text-sm text-gray-500 transition-colors hover:text-gray-900"
                    >
                      <Mail className="h-3.5 w-3.5 shrink-0" />
                      {email}
                    </a>
                  </li>
                )}
                {address && (
                  <li className="flex items-start gap-2 text-sm text-gray-500">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    {address}
                  </li>
                )}
              </ul>
            </div>

            {/* Menu */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-widest text-gray-400">
                Menu
              </h4>
              <ul className="space-y-3">
                {(menuLinks.length
                  ? menuLinks
                  : [{ label: "Full Menu", href: "/menu" }]
                ).map((link) => (
                  <li key={link.href}>
                    <Link
                      to={link.href}
                      className="text-sm text-gray-500 transition-colors hover:text-gray-900"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Company */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-widest text-gray-400">
                Company
              </h4>
              <ul className="space-y-3">
                {footerLinks.company.map((link) => (
                  <li key={link.href}>
                    <Link
                      to={link.href}
                      className="text-sm text-gray-500 transition-colors hover:text-gray-900"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Support */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-widest text-gray-400">
                Support
              </h4>
              <ul className="space-y-3">
                {footerLinks.support.map((link) => (
                  <li key={link.href}>
                    <Link
                      to={link.href}
                      className="text-sm text-gray-500 transition-colors hover:text-gray-900"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* ── Bottom bar ── */}
          <div className="flex flex-col items-center justify-between gap-3 border-t border-gray-100 pt-6 sm:flex-row">

            <p className="text-xs text-gray-300">
              {new Date().getFullYear()} {restaurantName}. All rights reserved.
            </p>

            {/* Social icons */}
            {socialLinks.length > 0 && (
              <div className="flex items-center gap-2">
                {socialLinks.map((social) => {
                  const Icon = social.icon;
                  return (
                    <a
                      key={social.label}
                      href={social.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={social.label}
                      className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 text-gray-400 transition-all hover:text-white"
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLAnchorElement).style.backgroundColor = primaryColor;
                        (e.currentTarget as HTMLAnchorElement).style.borderColor = primaryColor;
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLAnchorElement).style.backgroundColor = "";
                        (e.currentTarget as HTMLAnchorElement).style.borderColor = "";
                      }}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </a>
                  );
                })}
              </div>
            )}

            <p className="text-xs text-gray-300">Made with love</p>
          </div>

        </div>
      </footer>
    </>
  );
}