"use client";

import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import {
  X,
  CreditCard,
  Building2,
  Calendar,
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Check,
  Search,
} from "lucide-react";
import { formatINR, apiFetch } from "@/lib/api";

interface PaymentRecordModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialCustomerId?: string;
  initialInvoiceId?: string;
  onPaymentRecorded?: () => void;
}

export default function PaymentRecordModal({
  isOpen,
  onClose,
  initialCustomerId,
  initialInvoiceId,
  onPaymentRecorded,
}: PaymentRecordModalProps) {
  const [customers, setCustomers] = useState<any[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [amount, setAmount] = useState<string>("");
  const [receivedDate, setReceivedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [paymentMode, setPaymentMode] = useState<string>("neft");
  const [referenceNo, setReferenceNo] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const [invoices, setInvoices] = useState<any[]>([]);
  const [allocations, setAllocations] = useState<{ [invoiceId: string]: string }>({});
  const [isLoadingInvoices, setIsLoadingInvoices] = useState<boolean>(false);
  const [isSuggestingFifo, setIsSuggestingFifo] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load customer list
  useEffect(() => {
    if (isOpen) {
      loadCustomers();
      if (initialCustomerId) {
        setSelectedCustomerId(initialCustomerId);
      }
    }
  }, [isOpen, initialCustomerId]);

  // Load invoices when customer changes
  useEffect(() => {
    if (selectedCustomerId) {
      loadCustomerInvoices(selectedCustomerId);
    } else {
      setInvoices([]);
      setAllocations({});
    }
  }, [selectedCustomerId]);

  const loadCustomers = async () => {
    try {
      const data = await apiFetch<any>("/customers?page=1&page_size=200");
      setCustomers(data.items || []);
    } catch (err: any) {
      console.error("Failed to load customers:", err);
    }
  };

  const loadCustomerInvoices = async (custId: string) => {
    setIsLoadingInvoices(true);
    try {
      const data = await apiFetch<any>(`/invoices?customer_id=${custId}&status_filter=open&page=1&page_size=100`);
      // If status_filter=open is not supported, filter non-paid manually
      const openInvs = (data.items || []).filter(
        (inv: any) => inv.status !== "paid" && inv.status !== "cancelled"
      );
      setInvoices(openInvs);

      // If initialInvoiceId passed, pre-allocate
      if (initialInvoiceId && !amount) {
        const target = openInvs.find((i: any) => i.id === initialInvoiceId);
        if (target) {
          const bal = target.outstanding_balance || target.total_amount;
          setAmount(String(bal));
          setAllocations({ [initialInvoiceId]: String(bal) });
        }
      }
    } catch (err: any) {
      console.error("Failed to load invoices:", err);
    } finally {
      setIsLoadingInvoices(false);
    }
  };

  // FIFO auto-allocation suggestion
  const handleAutoAllocateFifo = async () => {
    const numAmt = parseFloat(amount);
    if (!selectedCustomerId || isNaN(numAmt) || numAmt <= 0) {
      setErrorMessage("Please select a retailer and enter a valid positive payment amount first.");
      return;
    }
    setErrorMessage(null);
    setIsSuggestingFifo(true);
    try {
      const data = await apiFetch<any>(
        `/payments/suggest-allocation?customer_id=${selectedCustomerId}&amount=${numAmt}`
      );
      const newAllocs: { [id: string]: string } = {};
      (data.allocations || []).forEach((item: any) => {
        if (parseFloat(item.suggested_allocated_amount) > 0) {
          newAllocs[item.invoice_id] = String(item.suggested_allocated_amount);
        }
      });
      setAllocations(newAllocs);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to calculate FIFO allocation");
    } finally {
      setIsSuggestingFifo(false);
    }
  };

  const handleAllocationChange = (invId: string, val: string) => {
    setAllocations((prev) => ({
      ...prev,
      [invId]: val,
    }));
  };

  // Calculations
  const paymentAmountNum = parseFloat(amount) || 0;
  const totalAllocatedNum = Object.values(allocations).reduce(
    (acc, val) => acc + (parseFloat(val) || 0),
    0
  );
  const unallocatedNum = Math.max(0, paymentAmountNum - totalAllocatedNum);
  const isOverAllocated = totalAllocatedNum > paymentAmountNum;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!selectedCustomerId) {
      setErrorMessage("Please select a customer.");
      return;
    }
    if (paymentAmountNum <= 0) {
      setErrorMessage("Payment amount must be greater than zero.");
      return;
    }
    if (isOverAllocated) {
      setErrorMessage("Total allocations exceed the total payment amount.");
      return;
    }

    // Format allocations
    const allocationPayload = Object.entries(allocations)
      .filter(([_, val]) => parseFloat(val) > 0)
      .map(([invId, val]) => ({
        invoice_id: invId,
        allocated_amount: parseFloat(val).toFixed(2),
      }));

    setIsSubmitting(true);
    try {
      await apiFetch("/payments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          received_date: receivedDate,
          amount: paymentAmountNum.toFixed(2),
          reference_no: referenceNo.trim() || null,
          payment_mode: paymentMode,
          notes: notes.trim() || null,
          allocations: allocationPayload,
        }),
      });

      setSuccessMessage("Payment recorded and ledger reconciled successfully!");
      if (onPaymentRecorded) onPaymentRecorded();
      setTimeout(() => {
        onClose();
        // Reset state
        setAmount("");
        setReferenceNo("");
        setNotes("");
        setAllocations({});
        setSuccessMessage(null);
      }, 1200);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to record payment");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const selectedCustomer = customers.find((c) => c.id === selectedCustomerId);

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 sm:p-6 overflow-y-auto"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-3xl shadow-dropdown max-w-2xl w-full border border-slate-200 overflow-hidden flex flex-col my-8"
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 34 }}
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 shadow-card">
              <CreditCard className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Record Payment & Allocate</h3>
              <p className="text-[11px] text-slate-500">
                Post customer remittance (NEFT/RTGS/UPI/Cheque) and match against open invoices
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Section 1: Customer & Amount */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Retailer / Customer <span className="text-rose-500">*</span>
              </label>
              <select
                value={selectedCustomerId}
                onChange={(e) => setSelectedCustomerId(e.target.value)}
                required
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all font-medium"
              >
                <option value="">Select Retailer...</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.gst_number ? `(${c.gst_number})` : ""}
                  </option>
                ))}
              </select>
              {selectedCustomer && (
                <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500 px-1">
                  <span>Credit Limit: {formatINR(selectedCustomer.credit_limit)}</span>
                  <span className="font-medium text-slate-700">Terms: Net {selectedCustomer.payment_terms_days}d</span>
                </div>
              )}
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Remittance Amount (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
                className="w-full text-xs font-mono font-bold bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all text-sm"
              />
            </div>
          </div>

          {/* Section 2: Mode, Date, Reference (UTR) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Payment Mode <span className="text-rose-500">*</span>
              </label>
              <select
                value={paymentMode}
                onChange={(e) => setPaymentMode(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 font-medium"
              >
                <option value="neft">NEFT Transfer</option>
                <option value="rtgs">RTGS Transfer</option>
                <option value="upi">UPI Remittance</option>
                <option value="cheque">Bank Cheque</option>
                <option value="cash">Cash Collection</option>
                <option value="other">Other / Adjustment</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Received Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                value={receivedDate}
                onChange={(e) => setReceivedDate(e.target.value)}
                required
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 font-mono"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                UTR / Reference No
              </label>
              <input
                type="text"
                placeholder="e.g. UTR123456789"
                value={referenceNo}
                onChange={(e) => setReferenceNo(e.target.value)}
                className="w-full text-xs font-mono bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </div>

          {/* Section 3: Invoices Allocation Table */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/50">
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between bg-white">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-slate-800">
                  Allocate Across Invoices ({invoices.length} open)
                </span>
              </div>
              <button
                type="button"
                onClick={handleAutoAllocateFifo}
                disabled={isSuggestingFifo || !amount || paymentAmountNum <= 0}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-brand-50 hover:bg-brand-100/80 text-brand-700 border border-brand-200/90 rounded-lg text-xs font-semibold shadow-card transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-3.5 h-3.5 text-brand-600" />
                <span>{isSuggestingFifo ? "Calculating..." : "Auto-Allocate FIFO"}</span>
              </button>
            </div>

            {isLoadingInvoices ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <div className="animate-spin w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full mx-auto mb-2" />
                Loading retailer's open invoices...
              </div>
            ) : invoices.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                {selectedCustomerId
                  ? "No unpaid invoices found for this customer. Any amount recorded will be tracked as an unallocated advance."
                  : "Select a customer to view open invoices."}
              </div>
            ) : (
              <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 bg-white">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500 sticky top-0">
                    <tr>
                      <th className="py-2 px-3">Invoice</th>
                      <th className="py-2 px-3">Due Date</th>
                      <th className="py-2 px-3 text-right">Outstanding</th>
                      <th className="py-2 px-3 text-right w-36">Allocate (₹)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {invoices.map((inv) => {
                      const bal = parseFloat(String(inv.outstanding_balance || inv.total_amount));
                      const allocatedVal = allocations[inv.id] || "";
                      return (
                        <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                          <td className="py-2.5 px-3 font-mono font-semibold text-slate-900">
                            #{inv.invoice_number}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">
                            {inv.due_date}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-800">
                            {formatINR(bal)}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              max={bal}
                              placeholder="0.00"
                              value={allocatedVal}
                              onChange={(e) => handleAllocationChange(inv.id, e.target.value)}
                              className="w-full text-right text-xs font-mono font-bold bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Allocation Balance Footer */}
            <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs">
              <div className="flex items-center space-x-4">
                <span>
                  Allocated:{" "}
                  <strong className="font-mono text-slate-900 font-bold">
                    {formatINR(totalAllocatedNum)}
                  </strong>
                </span>
                <span>
                  Unallocated Advance:{" "}
                  <strong
                    className={`font-mono font-bold ${
                      unallocatedNum > 0 ? "text-emerald-600" : "text-slate-500"
                    }`}
                  >
                    {formatINR(unallocatedNum)}
                  </strong>
                </span>
              </div>
              {isOverAllocated && (
                <span className="text-rose-600 font-semibold flex items-center space-x-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Allocations exceed payment!</span>
                </span>
              )}
            </div>
          </div>

          {/* Section 4: Notes */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Remarks / Notes
            </label>
            <input
              type="text"
              placeholder="e.g. Cleared via HDFC Bank statement, batch #412"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>

          {/* Feedback messages */}
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Modal Footer */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || isOverAllocated || paymentAmountNum <= 0}
              className="flex items-center space-x-1.5 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl text-xs font-semibold shadow-sm transition-all disabled:cursor-not-allowed"
            >
              <Check className="w-4 h-4" />
              <span>{isSubmitting ? "Recording..." : "Record Remittance"}</span>
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}
