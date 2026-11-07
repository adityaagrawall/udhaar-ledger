"use client";

import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import {
  X,
  Send,
  Copy,
  Check,
  Sparkles,
  MessageSquare,
  Smartphone,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileCheck2,
} from "lucide-react";
import { formatINR, apiFetch } from "@/lib/api";
import { useMe } from "@/components/Providers";

interface ReminderModalProps {
  isOpen: boolean;
  onClose: () => void;
  invoice: {
    id: string;
    invoice_number: string;
    customer_id?: string;
    customer_name: string;
    customer_phone?: string;
    outstanding_balance: number | string;
    due_date: string;
    days_overdue: number;
    open_follow_up_id?: string;
  } | null;
  onFollowUpUpdated?: () => void;
}

export default function ReminderModal({
  isOpen,
  onClose,
  invoice,
  onFollowUpUpdated,
}: ReminderModalProps) {
  const [channel, setChannel] = useState<"whatsapp" | "sms">("whatsapp");
  const [language, setLanguage] = useState<"english" | "hindi">("english");
  const [phone, setPhone] = useState<string>("");
  const [draft, setDraft] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [approved, setApproved] = useState<boolean>(false);
  const { canEdit } = useMe();
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && invoice) {
      setPhone(invoice.customer_phone || "+91 98765 43210");
      fetchDraft();
      setApproved(false);
      setSuccessMessage(null);
      setErrorMessage(null);
    }
  }, [isOpen, invoice, channel, language]);

  const handleOpenWhatsApp = () => {
    let clean = phone.replace(/[^0-9]/g, "");
    if (clean.length === 10) clean = "91" + clean;
    const url = `https://wa.me/${clean}?text=${encodeURIComponent(draft)}`;
    window.open(url, "_blank");
    setApproved(true);
  };

  const fetchDraft = async () => {
    if (!invoice) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (invoice.open_follow_up_id) {
        const res = await apiFetch<any>("/reminders/draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            follow_up_id: invoice.open_follow_up_id,
            channel,
            language,
          }),
        });
        setDraft(res.draft);
      } else {
        const dueFormatted = new Date(invoice.due_date).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
        });
        const amtStr = formatINR(invoice.outstanding_balance);

        if (language === "hindi") {
          setDraft(
            `नमस्ते ${invoice.customer_name},\n\nयह शर्मा डिस्ट्रीब्यूटर्स से एक विनम्र अनुस्मारक है। आपका चालान #${invoice.invoice_number} की राशि ${amtStr} जो ${dueFormatted} को देय थी (${invoice.days_overdue} दिन अतिदेय), अभी तक प्राप्त नहीं हुई है।\n\nकृपया आरटीजीएस/एनईएफटी या यूपीआई के माध्यम से शीघ्र भुगतान करने की कृपा करें।\n\nधन्यवाद,\nशर्मा डिस्ट्रीब्यूटर्स प्राइवेट लिमिटेड`
          );
        } else {
          setDraft(
            `Dear ${invoice.customer_name},\n\nThis is a gentle payment reminder from our team regarding Invoice #${invoice.invoice_number} for ${amtStr}, which was due on ${dueFormatted} (${invoice.days_overdue} days overdue).\n\nPlease process the payment at your earliest convenience via NEFT/RTGS/UPI.\n\nThank you for your business,\nAccounts Team, our team Pvt Ltd`
          );
        }
      }
    } catch (err: any) {
      console.error("Draft error:", err);
      setDraft(
        `Dear ${invoice.customer_name}, Invoice #${invoice.invoice_number} for ${formatINR(
          invoice.outstanding_balance
        )} is overdue. Kindly expedite payment. our team.`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApproveAndLog = async () => {
    if (!invoice) return;
    setIsApproving(true);
    setErrorMessage(null);

    try {
      if (invoice.open_follow_up_id) {
        await apiFetch(`/reminders/approve/${invoice.open_follow_up_id}`, {
          method: "POST",
        });
      } else {
        // If customer_id not on invoice, look up invoice details
        let custId = invoice.customer_id;
        if (!custId) {
          const invData = await apiFetch<any>(`/invoices/${invoice.id}`);
          custId = invData.customer_id;
        }
        await apiFetch("/follow-ups", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            invoice_id: invoice.id,
            customer_id: custId,
            channel,
            status: "contacted",
            notes: `Dispatched reminder via ${channel.toUpperCase()} (${language}) to ${phone}. Human approved.`,
          }),
        });
      }
      setSuccessMessage("Reminder logged and customer marked as Contacted.");
      if (onFollowUpUpdated) onFollowUpUpdated();
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to approve reminder");
    } finally {
      setIsApproving(false);
    }
  };

  if (!isOpen || !invoice) return null;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 sm:p-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-3xl shadow-dropdown max-w-lg w-full overflow-hidden border border-slate-200 flex flex-col"
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 34 }}
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Grounded Reminder Assistant</h3>
              <p className="text-[11px] text-slate-500 font-mono">
                #{invoice.invoice_number} • {invoice.customer_name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          {/* Fact card */}
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/80 flex items-center justify-between text-xs">
            <div>
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Outstanding</span>
              <span className="text-sm font-bold font-mono text-slate-900 block mt-0.5">
                {formatINR(invoice.outstanding_balance)}
              </span>
            </div>
            <div className="text-right">
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Due Status</span>
              <span className="text-xs font-semibold text-rose-600 block mt-0.5">
                {invoice.days_overdue}d overdue
              </span>
            </div>
          </div>

          {/* Delivery & Language selectors */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="text-[11px] font-semibold text-slate-700 block mb-1">
                Channel
              </label>
              <div className="grid grid-cols-2 gap-1 p-0.5 bg-slate-100 rounded-lg">
                <button
                  type="button"
                  onClick={() => setChannel("whatsapp")}
                  className={`py-1.5 flex items-center justify-center space-x-1 rounded-md text-xs font-medium transition-colors ${
                    channel === "whatsapp"
                      ? "bg-white text-emerald-700 shadow-card font-semibold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>WhatsApp</span>
                </button>
                <button
                  type="button"
                  onClick={() => setChannel("sms")}
                  className={`py-1.5 flex items-center justify-center space-x-1 rounded-md text-xs font-medium transition-colors ${
                    channel === "sms"
                      ? "bg-white text-slate-900 shadow-card font-semibold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Smartphone className="w-3.5 h-3.5" />
                  <span>SMS</span>
                </button>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-700 block mb-1">
                Language
              </label>
              <div className="grid grid-cols-2 gap-1 p-0.5 bg-slate-100 rounded-lg">
                <button
                  type="button"
                  onClick={() => setLanguage("english")}
                  className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                    language === "english"
                      ? "bg-white text-brand-700 shadow-card font-semibold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  English
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage("hindi")}
                  className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                    language === "hindi"
                      ? "bg-white text-brand-700 shadow-card font-semibold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  हिंदी
                </button>
              </div>
            </div>
          </div>

          {/* Recipient Phone & Direct Dispatch */}
          {channel === "whatsapp" && (
            <div className="p-3 bg-emerald-50/70 border border-emerald-200/80 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-emerald-950 flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />
                  Direct WhatsApp Dispatch (wa.me)
                </span>
                <span className="text-[10px] text-emerald-700">Official Click-to-Chat</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="flex-1 text-xs font-mono bg-white border border-emerald-300 rounded-lg px-2.5 py-1.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
                <button
                  type="button"
                  onClick={handleOpenWhatsApp}
                  disabled={!draft.trim() || !phone.trim()}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-card transition-all disabled:opacity-50"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Launch WhatsApp</span>
                </button>
              </div>
            </div>
          )}

          {/* Draft text area */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-semibold text-slate-700">Editable Message Draft</span>
              <button
                type="button"
                onClick={handleCopy}
                className="text-xs text-brand-600 hover:text-brand-800 flex items-center gap-1 font-medium transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <div className="relative">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={5}
                className="w-full text-xs font-mono bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all leading-relaxed"
                placeholder="Drafting message..."
                disabled={isLoading}
              />
              {isLoading && (
                <div className="absolute inset-0 bg-white/70 backdrop-blur-[1px] flex items-center justify-center rounded-xl text-xs text-slate-600 font-medium">
                  <div className="animate-spin w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full mr-2" />
                  Generating grounded draft...
                </div>
              )}
            </div>
          </div>

          {/* Safety Notice & Approval Checkbox */}
          <div className="p-3 bg-amber-50/70 border border-amber-200/80 rounded-xl text-xs space-y-2">
            <div className="flex items-start space-x-2">
              <ShieldCheck className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-[11px] text-amber-900">
                <span className="font-semibold block">Human Review Required</span>
                Facts and amounts are grounded in verified invoice records. Reminders are recorded only after human approval.
              </div>
            </div>

            <label className="flex items-center space-x-2 pt-1.5 border-t border-amber-200/60 cursor-pointer">
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
                className="w-4 h-4 text-brand-500 rounded border-slate-300 focus:ring-brand-500 cursor-pointer"
              />
              <span className="text-[11px] font-medium text-slate-800 select-none">
                I verify the amounts and approve recording this follow-up
              </span>
            </label>
          </div>

          {/* Feedback messages */}
          {successMessage && (
            <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}
          {errorMessage && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-border flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Cancel
          </button>

          {!canEdit ? (
            <span className="text-[11px] text-slate-500">Read-only access: you can copy the draft, but not log it.</span>
          ) : (
          <button
            type="button"
            onClick={handleApproveAndLog}
            disabled={!approved || isApproving || !draft.trim()}
            className="flex items-center space-x-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isApproving ? "Logging..." : "Approve & Mark Contacted"}</span>
          </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
