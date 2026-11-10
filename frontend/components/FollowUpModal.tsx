"use client";

import Modal, { ModalTitle } from "@/components/Modal";
import { useState, useEffect } from "react";
import {
  X,
  PhoneCall,
  Calendar,
  IndianRupee,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  MessageSquare,
  UserCheck,
  Check,
} from "lucide-react";
import { formatINR, apiFetch } from "@/lib/api";

interface FollowUpModalProps {
  isOpen: boolean;
  onClose: () => void;
  invoice: {
    id: string;
    invoice_number: string;
    customer_id: string;
    customer_name: string;
    outstanding_balance: number | string;
  } | null;
  onFollowUpCreated?: () => void;
}

export default function FollowUpModal({
  isOpen,
  onClose,
  invoice,
  onFollowUpCreated,
}: FollowUpModalProps) {
  const [channel, setChannel] = useState<string>("call");
  const [status, setStatus] = useState<string>("contacted");
  const [notes, setNotes] = useState<string>("");
  const [hasPromise, setHasPromise] = useState<boolean>(false);
  const [promisedAmount, setPromisedAmount] = useState<string>("");
  const [promisedDate, setPromisedDate] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && invoice) {
      setChannel("call");
      setStatus("contacted");
      setNotes("");
      setHasPromise(false);
      setPromisedAmount(String(invoice.outstanding_balance || ""));
      const nextWeek = new Date();
      nextWeek.setDate(nextWeek.getDate() + 7);
      setPromisedDate(nextWeek.toISOString().split("T")[0]);
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [isOpen, invoice]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoice) return;

    setErrorMessage(null);
    setSuccessMessage(null);

    const payload: any = {
      invoice_id: invoice.id,
      customer_id: invoice.customer_id,
      channel,
      status: hasPromise ? "promised" : status,
      notes: notes.trim() || (hasPromise ? `Promise-to-Pay registered for ₹${promisedAmount} on ${promisedDate}` : "Follow-up contact logged"),
    };

    if (hasPromise) {
      const amtNum = parseFloat(promisedAmount);
      if (isNaN(amtNum) || amtNum <= 0) {
        setErrorMessage("Please enter a valid positive promised amount.");
        return;
      }
      if (!promisedDate) {
        setErrorMessage("Please select the committed payment date.");
        return;
      }
      payload.promised_amount = amtNum.toFixed(2);
      payload.promised_date = promisedDate;
      payload.promise_status = "pending";
    }

    setIsSubmitting(true);
    try {
      await apiFetch("/follow-ups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setSuccessMessage(
        hasPromise
          ? "Promise-to-Pay recorded successfully! Priority queue updated."
          : "Follow-up activity logged successfully!"
      );
      if (onFollowUpCreated) onFollowUpCreated();
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to log follow-up");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !invoice) return null;

  return (
    <Modal onClose={onClose} className="bg-white rounded-3xl shadow-dropdown max-w-lg w-full border border-slate-200 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600">
              <PhoneCall className="w-4 h-4" />
            </div>
            <div>
              <ModalTitle className="font-bold text-slate-900 text-sm">Log Collection Follow-up</ModalTitle>
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Outstanding Summary */}
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/80 flex items-center justify-between text-xs">
            <div>
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Outstanding Due</span>
              <span className="text-sm font-bold font-mono text-slate-900 block mt-0.5">
                {formatINR(invoice.outstanding_balance)}
              </span>
            </div>
            <div className="text-right">
              <span className="text-slate-400 text-[10px] uppercase font-semibold">Account</span>
              <span className="text-xs font-semibold text-slate-700 block mt-0.5 truncate max-w-[180px]">
                {invoice.customer_name}
              </span>
            </div>
          </div>

          {/* Channel & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Channel
              </label>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 font-medium"
              >
                <option value="call">Phone Call</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="sms">SMS</option>
                <option value="in_person">In-Person Visit</option>
                <option value="email">Email</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Contact Outcome
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                disabled={hasPromise}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 font-medium disabled:opacity-60"
              >
                <option value="contacted">Spoke with Retailer</option>
                <option value="pending">Left Message / No Answer</option>
                <option value="escalated">Disputed / Escalated</option>
                <option value="resolved">Resolved / Already Paid</option>
              </select>
            </div>
          </div>

          {/* PTP Toggle Card */}
          <div className="border border-brand-200 bg-brand-50/40 rounded-xl p-3.5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-brand-600" />
                <span className="text-xs font-bold text-brand-950">
                  Promise-to-Pay (PTP) Commitment
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasPromise}
                  onChange={(e) => setHasPromise(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-brand-500" />
              </label>
            </div>

            {hasPromise && (
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-brand-100">
                <div>
                  <label className="text-[11px] font-semibold text-slate-700 block mb-1">
                    Promised Amount (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="1"
                    value={promisedAmount}
                    onChange={(e) => setPromisedAmount(e.target.value)}
                    required={hasPromise}
                    className="w-full text-xs font-mono font-bold bg-white border border-brand-200 rounded-lg px-2.5 py-1.5 text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-700 block mb-1">
                    Committed Payment Date
                  </label>
                  <input
                    type="date"
                    value={promisedDate}
                    onChange={(e) => setPromisedDate(e.target.value)}
                    required={hasPromise}
                    min={new Date().toISOString().split("T")[0]}
                    className="w-full text-xs font-mono bg-white border border-brand-200 rounded-lg px-2.5 py-1.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Collector Notes & Conversation Summary
            </label>
            <textarea
              rows={3}
              placeholder="e.g. Spoke with proprietor Rajesh. Stated stock sale proceeds will clear by Friday. Committed to UPI transfer."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 leading-relaxed"
            />
          </div>

          {/* Feedback messages */}
          {errorMessage && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
          {successMessage && (
            <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Footer */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center space-x-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:cursor-not-allowed"
            >
              <Check className="w-3.5 h-3.5" />
              <span>{isSubmitting ? "Logging..." : "Save Follow-up"}</span>
            </button>
          </div>
        </form>
      </Modal>
  );
}
