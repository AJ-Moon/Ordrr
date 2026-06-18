import { useState, useEffect } from "react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapPin, Phone, Mail, Clock, Send, CheckCircle2 } from "lucide-react";
import { useRestaurant } from "@/contexts/RestaurantContext";

export default function ContactPage() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [subject, setSubject] = useState("");
  const { primaryColor, phone, email, address, mapsEmbed, contactHoursNote } =
    useRestaurant() as any;

  const contactInfo = [
    {
      icon: Phone,
      label: "Phone",
      value: phone || "",
      description: contactHoursNote || "",
    },
    {
      icon: Mail,
      label: "Email",
      value: email || "",
      description: "We reply within 24 hours",
    },
    {
      icon: MapPin,
      label: "Address",
      value: address || "",
      description: "",
    },
    {
      icon: Clock,
      label: "Hours",
      value: contactHoursNote || "",
      description: "Daily, including holidays",
    },
  ].filter((item) => item.value);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const firstName = (form.elements.namedItem("firstName") as HTMLInputElement)
      .value;
    const lastName = (form.elements.namedItem("lastName") as HTMLInputElement)
      .value;
    const data = {
      name: `${firstName} ${lastName}`.trim(),
      email: (form.elements.namedItem("email") as HTMLInputElement).value,
      subject: subject || "General Inquiry",
      message: (form.elements.namedItem("message") as HTMLTextAreaElement)
        .value,
    };
    try {
      await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    } catch {
      // fail silently in demo
    }
    setIsSubmitted(true);
    setTimeout(() => setIsSubmitted(false), 3000);
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pb-20 md:pb-0">
        {/* Hero */}
        <section className="bg-accent py-12 lg:py-16">
          <div className="mx-auto max-w-7xl px-4 text-center lg:px-8">
            <h1 className="font-serif text-4xl font-extrabold text-accent-foreground sm:text-5xl">
              Contact Us
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-accent-foreground/70">
              Have a question, feedback, or just want to say hello? We&apos;d
              love to hear from you.
            </p>
          </div>
        </section>

        {/* Contact Section */}
        <section className="py-12 lg:py-16">
          <div className="mx-auto max-w-7xl px-4 lg:px-8">
            <div className="grid gap-12 lg:grid-cols-2">
              {/* Contact Form */}
              <div className="order-2 lg:order-1">
                <h2 className="font-serif text-2xl font-bold text-foreground">
                  Send us a message
                </h2>
                <p className="mt-2 text-muted-foreground">
                  Fill out the form and our team will get back to you shortly.
                </p>

                {isSubmitted ? (
                  <div className="mt-8 flex flex-col items-center justify-center rounded-2xl border border-green-200 bg-green-50 p-12 text-center">
                    <CheckCircle2 className="h-16 w-16 text-green-500" />
                    <h3 className="mt-4 font-serif text-2xl font-bold text-foreground">
                      Message Sent!
                    </h3>
                    <p className="mt-2 text-muted-foreground">
                      We'll get back to you within 24 hours.
                    </p>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="mt-8 space-y-6">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="firstName">First Name</Label>
                        <Input
                          id="firstName"
                          name="firstName"
                          placeholder="John"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="lastName">Last Name</Label>
                        <Input
                          id="lastName"
                          name="lastName"
                          placeholder="Doe"
                          required
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        placeholder="john@example.com"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="subject">Subject</Label>
                      <Select value={subject} onValueChange={setSubject}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a subject" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="general">
                            General Inquiry
                          </SelectItem>
                          <SelectItem value="order">Order Issue</SelectItem>
                          <SelectItem value="feedback">Feedback</SelectItem>
                          <SelectItem value="partnership">
                            Partnership
                          </SelectItem>
                          <SelectItem value="careers">Careers</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="message">Message</Label>
                      <Textarea
                        id="message"
                        name="message"
                        placeholder="Tell us how we can help..."
                        rows={5}
                        required
                      />
                    </div>
                    <Button
                      type="submit"
                      size="lg"
                      className="w-full text-white"
                      style={{ backgroundColor: primaryColor }}
                    >
                      <Send className="mr-2 h-4 w-4" />
                      Send Message
                    </Button>
                  </form>
                )}
              </div>

              {/* Contact Info + Map */}
              <div className="order-1 lg:order-2">
                <h2 className="font-serif text-2xl font-bold text-foreground">
                  Get in touch
                </h2>
                <p className="mt-2 text-muted-foreground">
                  Prefer to reach us directly? Here are our contact details.
                </p>

                <div className="mt-8 space-y-6">
                  {contactInfo.map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.label} className="flex gap-4">
                        <div
                          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
                          style={{ backgroundColor: `${primaryColor}15` }}
                        >
                          <Icon
                            className="h-5 w-5"
                            style={{ color: primaryColor }}
                          />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">
                            {item.label}
                          </p>
                          <p className="font-semibold text-foreground">
                            {item.value}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {item.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Google Maps embed — only rendered if maps_embed is set in /api/settings */}
                {mapsEmbed && (
                  <div className="mt-8 overflow-hidden rounded-2xl border border-border shadow-sm">
                    <iframe
                      src={mapsEmbed}
                      width="100%"
                      height="300"
                      loading="lazy"
                      referrerPolicy="no-referrer-when-downgrade"
                      className="w-full"
                      title="Location map"
                      style={{ border: 0 }}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
