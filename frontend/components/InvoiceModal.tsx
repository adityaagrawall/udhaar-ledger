"use client";

import Modal, { ModalTitle } from "@/components/Modal";
import { useEffect, useState } from "react";
import {
  X,
  Receipt,
  Calendar,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  CreditCard,
  Building2,
  FileText,
  ShieldCheck,
  Hash,
} from "lucide-react";
import { formatINR, formatDate, apiFetch } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";

interface InvoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  invoiceId: string | null;
  onDraftReminder?: (invoice: any) => void;
}

export default function InvoiceModal({
  isOpen,
  onClose,
  invoiceId,
  onDraftReminder,
}: InvoiceModalProps) {
  const [invoice, setInvoice] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && invoiceId) {
      loadInvoiceDetails();
    }
  }, [isOpen, invoiceId]);

  const loadInvoiceDetails = async () => {
    if (!invoiceId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<any>(`/invoices/${invoiceId}`);
      setInvoice(data);
    } catch (err: any) {
      setError(err.message || "Failed to load invoice details");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const totalAllocated =
    invoice?.allocations?.reduce(
      (acc: number, curr: any) => acc + parseFloat(curr.allocated_amount),
      0
    ) || 0;

  return (
    <Modal onClose={onClose} className="bg-white rounded-3xl shadow-dropdown max-w-2xl w-full overflow-hidden border border-slate-200 flex flex-col max-h-[90vh]">
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 flex-shrink-0">
              <Receipt className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <ModalTitle className="font-bold text-slate-900 text-sm font-mono tracking-tight truncate">
                  {invoice?.invoice_number || "Invoice Details"}
                </ModalTitle>
                {invoice && <StatusBadge status={invoice.status} />}
              </div>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {invoice?.customer_name || "Loading..."}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1">
          {isLoading ? (
            <div className="py-20 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-2">
              <div className="animate-spin w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full" />
              <span>Fetching verified financial records...</span>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-50 text-rose-700 text-xs rounded-xl border border-rose-200 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          ) : invoice ? (
            <>
              {/* Financial Balance Summary Card */}
              <div className="grid grid-cols-3 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200/80">
                <div>
                  <span className="text-[11px] font-medium text-slate-500 block">
                    Invoice Gross
                  </span>
                  <span className="text-base font-bold font-mono text-slate-900 mt-0.5 block">
                    {formatINR(invoice.total_amount)}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-medium text-emerald-700 block">
                    Paid to Date
                  </span>
                  <span className="text-base font-bold font-mono text-emerald-700 mt-0.5 block">
                    {formatINR(totalAllocated)}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-medium text-rose-700 block">
                    Outstanding Balance
                  </span>
                  <span className="text-base font-bold font-mono text-rose-700 mt-0.5 block">
                    {formatINR(invoice.outstanding_balance)}
                  </span>
                </div>
              </div>

              {/* Dates & Credit Terms */}
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3 bg-white rounded-xl border border-slate-200 flex items-center space-x-3">
                  <Calendar className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <div>
                    <span className="text-[11px] text-slate-500 block">Issue Date</span>
                    <span className="font-semibold text-slate-800">
                      {formatDate(invoice.issue_date)}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-white rounded-xl border border-slate-200 flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <div>
                    <span className="text-[11px] text-slate-500 block">Due Date</span>
                    <span className="font-semibold text-slate-800">
                      {formatDate(invoice.due_date)}
                      {invoice.days_overdue > 0 && (
                        <span className="ml-1 text-rose-600 font-bold">
                          ({invoice.days_overdue}d overdue)
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </div>

              {/* Payment Allocations Ledger */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <span>Payment Allocations Ledger</span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      (Deterministic Subquery)
                    </span>
                  </h4>
                  <span className="text-[10px] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 font-medium">
                    {invoice.allocations?.length || 0} Records
                  </span>
                </div>

                {invoice.allocations && invoice.allocations.length > 0 ? (
                  <div className="border border-slate-200 rounded-xl overflow-hidden shadow-card">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold">
                        <tr>
                          <th scope="col" className="py-2.5 px-3.5">Allocation ID</th>
                          <th scope="col" className="py-2.5 px-3.5">Date Allocated</th>
                          <th scope="col" className="py-2.5 px-3.5 text-right">Amount Allocated</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {invoice.allocations.map((alloc: any) => (
                          <tr key={alloc.id} className="hover:bg-slate-50/50">
                            <td className="py-2.5 px-3.5 font-mono text-[11px] text-slate-600">
                              #{alloc.id.slice(0, 8)}
                            </td>
                            <td className="py-2.5 px-3.5 text-slate-700">
                              {formatDate(alloc.allocated_at)}
                            </td>
                            <td className="py-2.5 px-3.5 text-right font-mono font-bold text-emerald-700">
                              {formatINR(alloc.allocated_amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-400">
                    No payment allocations recorded yet. Outstanding balance equals the full invoice gross.
                  </div>
                )}
              </div>

              {/* Notes block if present */}
              {invoice.notes && (
                <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-0.5">
                  <span className="font-semibold text-slate-700 block text-[11px]">
                    Internal Notes
                  </span>
                  <p>{invoice.notes}</p>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-border flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Close
          </button>

          {invoice && invoice.status !== "paid" && onDraftReminder && (
            <button
              onClick={() => {
                onClose();
                onDraftReminder(invoice);
              }}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Draft AI Reminder</span>
            </button>
          )}
        </div>
      </Modal>
  );
}
