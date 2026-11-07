"use client";

import { useEffect, useRef, useState, DragEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  UploadCloud,
  FileSpreadsheet,
  X,
  Check,
  AlertTriangle,
  Download,
  Copy,
  CheckCircle2,
  Lock,
  History,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Badge from "@/components/Badge";
import { useMe } from "@/components/Providers";
import { PageBody, Card, SectionTitle, ErrorBanner, SkeletonRows, tbl } from "@/components/ui";
import { apiFetch, formatDate } from "@/lib/api";

const SAMPLE = `invoice_number,customer_name,customer_email,issue_date,due_date,total_amount,payment_amount,payment_date,payment_reference,payment_mode
INV-SAMPLE-101,Aman Wholesale Ltd,aman@sample.in,2024-03-01,2024-03-31,120000.00,40000.00,2024-03-15,UTR-SMP-991,neft
INV-SAMPLE-102,Gupta Hardware Mart,gupta@sample.in,2024-03-05,2024-04-05,85000.00,,,,
INV-SAMPLE-103,Bansal Pharma Dist,bansal@sample.in,2024-03-10,2024-04-10,250000.00,250000.00,2024-04-02,UTR-SMP-992,rtgs
INV-SAMPLE-104,Patel Agro Supplies,patel@sample.in,2024-03-15,2024-04-15,64000.00,,,,`;

const COLUMNS = [
  ["invoice_number", "Required", "Unique per organisation"],
  ["customer_name", "Required", "Matched to existing customers by name"],
  ["issue_date / due_date", "Required", "YYYY-MM-DD or DD/MM/YYYY"],
  ["total_amount", "Required", "Positive number; commas and ₹ allowed"],
  ["payment_amount", "Optional", "Cannot exceed total_amount"],
  ["payment_date", "If paid", "Required whenever payment_amount is given"],
  ["payment_reference / mode", "Optional", "UTR and neft / rtgs / upi / cheque / cash"],
];

const STEPS = ["Upload", "Review", "Done"];

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-3">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const done = step > n;
        const active = step === n;
        return (
          <li key={label} className="flex items-center gap-3">
            <span className="flex items-center gap-2">
              <span
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                  done ? "bg-emerald-500 text-white" : active ? "bg-brand-700 text-white" : "bg-background text-slate-400 ring-1 ring-border"
                }`}
              >
                {done ? <Check className="w-3.5 h-3.5" /> : n}
              </span>
              <span className={`text-xs font-semibold ${active ? "text-ink-900" : "text-slate-500"}`}>{label}</span>
            </span>
            {n < STEPS.length && <span className="w-10 h-px bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

export default function ImportPage() {
  const { canEdit, loading: meLoading } = useMe();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [committing, setCommitting] = useState(false);
  const [done, setDone] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadJobs = async () => {
    setJobsLoading(true);
    try {
      const data = await apiFetch<any>("/import/jobs");
      setJobs(data.items || []);
    } catch {
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const pick = (f: File) => {
    if (![".csv", ".xlsx", ".xls"].some((ext) => f.name.toLowerCase().endsWith(ext))) {
      setError("Upload a CSV or Excel file (.csv, .xlsx, .xls).");
      return;
    }
    setFile(f);
    setPreview(null);
    setDone(null);
    setError(null);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.[0]) pick(e.dataTransfer.files[0]);
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      setPreview(await apiFetch<any>("/import/preview", { method: "POST", body: form }));
    } catch (e: any) {
      setError(e.message || "Could not read the file");
    } finally {
      setUploading(false);
    }
  };

  const commit = async () => {
    if (!preview?.preview_token) return;
    setCommitting(true);
    setError(null);
    try {
      const job = await apiFetch<any>("/import/commit", {
        method: "POST",
        body: JSON.stringify({ preview_token: preview.preview_token }),
      });
      setDone(job);
      setPreview(null);
      setFile(null);
      loadJobs();
    } catch (e: any) {
      setError(e.message || "Import failed");
    } finally {
      setCommitting(false);
    }
  };

  const downloadSample = () => {
    const url = URL.createObjectURL(new Blob([SAMPLE], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "udhaar_ledger_import_sample.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const step = done ? 3 : preview ? 2 : 1;
  const realErrors = (preview?.errors || []).filter((e: any) => !String(e.message).startsWith("Duplicate"));
  const dupes = (preview?.errors || []).filter((e: any) => String(e.message).startsWith("Duplicate"));

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Import"
        subtitle="Bring invoices and receipts in from Tally or Excel exports"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Books" }, { label: "Import" }]}
        onRefresh={loadJobs}
        isRefreshing={jobsLoading}
      />

      <PageBody>
        <div className="grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-5">
          <Card className="!p-0 overflow-hidden">
            <div className="px-5 py-4 border-b border-border-light flex flex-wrap items-center justify-between gap-3">
              <Stepper step={step} />
              <button
                onClick={downloadSample}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border border-border bg-white hover:bg-background text-xs font-semibold text-ink-900"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" /> Sample CSV
              </button>
            </div>

            <div className="p-5 space-y-4">
              {error && <ErrorBanner message={error} />}

              {!meLoading && !canEdit ? (
                <div className="py-14 text-center">
                  <span className="w-12 h-12 mx-auto rounded-2xl bg-background ring-1 ring-border flex items-center justify-center">
                    <Lock className="w-5 h-5 text-slate-400" />
                  </span>
                  <p className="mt-3 text-sm font-semibold text-ink-900">Importing is disabled in read-only access</p>
                  <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                    You can still download the sample file to see the format, and browse previous imports on the right.
                  </p>
                </div>
              ) : (
                <AnimatePresence mode="wait">
                  {step === 1 && (
                    <motion.div key="upload" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                      <div
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragging(true);
                        }}
                        onDragLeave={() => setDragging(false)}
                        onDrop={onDrop}
                        onClick={() => inputRef.current?.click()}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
                        className={`relative rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
                          dragging ? "border-brand-500 bg-brand-50/60" : "border-border hover:border-brand-300 hover:bg-background"
                        }`}
                      >
                        <motion.span
                          animate={dragging ? { y: -4, scale: 1.05 } : { y: 0, scale: 1 }}
                          className="w-14 h-14 mx-auto rounded-2xl bg-brand-50 text-brand-600 ring-1 ring-brand-200 flex items-center justify-center"
                        >
                          <UploadCloud className="w-6 h-6" />
                        </motion.span>
                        <p className="mt-4 text-sm font-semibold text-ink-900">Drop a CSV or Excel file, or click to browse</p>
                        <p className="mt-1 text-xs text-slate-500">Nothing is saved until you review and confirm.</p>
                        <input
                          ref={inputRef}
                          type="file"
                          accept=".csv,.xlsx,.xls"
                          className="hidden"
                          onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])}
                        />
                      </div>

                      {file && (
                        <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-background ring-1 ring-border">
                          <span className="flex items-center gap-3 min-w-0">
                            <FileSpreadsheet className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                            <span className="min-w-0">
                              <span className="block text-sm font-semibold text-ink-900 truncate">{file.name}</span>
                              <span className="block text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB</span>
                            </span>
                          </span>
                          <span className="flex items-center gap-2">
                            <button onClick={reset} aria-label="Remove file" className="h-9 w-9 rounded-lg hover:bg-white text-slate-500 flex items-center justify-center">
                              <X className="w-4 h-4" />
                            </button>
                            <button
                              onClick={upload}
                              disabled={uploading}
                              className="h-9 px-4 rounded-xl bg-brand-700 hover:bg-brand-600 text-white text-xs font-semibold disabled:opacity-60"
                            >
                              {uploading ? "Validating…" : "Validate file"}
                            </button>
                          </span>
                        </div>
                      )}
                    </motion.div>
                  )}

                  {step === 2 && preview && (
                    <motion.div key="review" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {[
                          ["Rows read", preview.total_rows, "text-ink-900"],
                          ["Ready to import", preview.valid_rows, "text-emerald-700"],
                          ["With errors", preview.error_rows, preview.error_rows ? "text-rose-600" : "text-slate-400"],
                          ["Duplicates skipped", preview.duplicate_rows, preview.duplicate_rows ? "text-accent-700" : "text-slate-400"],
                        ].map(([k, v, c]) => (
                          <div key={k as string} className="rounded-xl bg-background ring-1 ring-border p-3">
                            <p className="text-[11px] text-slate-500">{k}</p>
                            <p className={`mt-1 text-xl font-semibold font-mono tabular ${c}`}>{v as number}</p>
                          </div>
                        ))}
                      </div>

                      {realErrors.length > 0 && (
                        <div className="rounded-xl ring-1 ring-rose-200 bg-rose-50/50 overflow-hidden">
                          <p className="px-4 py-2.5 text-xs font-semibold text-rose-800 flex items-center gap-2 border-b border-rose-200">
                            <AlertTriangle className="w-3.5 h-3.5" /> These rows will not be imported
                          </p>
                          <ul className="max-h-48 overflow-y-auto divide-y divide-rose-100 text-xs">
                            {realErrors.slice(0, 50).map((e: any, i: number) => (
                              <li key={i} className="px-4 py-2 flex gap-3">
                                <span className="font-mono text-rose-700 w-14 flex-shrink-0">Row {e.row_index}</span>
                                <span className="font-mono text-slate-500 w-28 flex-shrink-0 truncate">{e.field}</span>
                                <span className="text-slate-700">{e.message}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {dupes.length > 0 && (
                        <p className="text-xs text-accent-700 flex items-center gap-2">
                          <Copy className="w-3.5 h-3.5" /> {dupes.length} invoice number{dupes.length === 1 ? "" : "s"} already exist or repeat in the file and will be skipped.
                        </p>
                      )}

                      {preview.sample_data?.length > 0 && (
                        <div className="rounded-xl ring-1 ring-border overflow-x-auto">
                          <table className={tbl.table}>
                            <thead className={tbl.thead}>
                              <tr>
                                {["Invoice", "Customer", "Issued", "Due", "Amount", "Paid"].map((h) => (
                                  <th key={h} className={tbl.th}>
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {preview.sample_data.map((r: any, i: number) => (
                                <tr key={i} className={tbl.tr}>
                                  <td className={`${tbl.td} font-mono text-xs`}>{r.invoice_number}</td>
                                  <td className={`${tbl.td} text-xs`}>{r.customer_name}</td>
                                  <td className={`${tbl.td} text-xs text-slate-500`}>{r.issue_date}</td>
                                  <td className={`${tbl.td} text-xs text-slate-500`}>{r.due_date}</td>
                                  <td className={`${tbl.td} font-mono text-xs tabular`}>{r.total_amount}</td>
                                  <td className={`${tbl.td} font-mono text-xs tabular text-emerald-700`}>{r.payment_amount ?? "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button onClick={reset} className="h-10 px-4 rounded-xl border border-border bg-white hover:bg-background text-xs font-semibold">
                          Start over
                        </button>
                        <button
                          onClick={commit}
                          disabled={committing || preview.valid_rows === 0}
                          className="h-10 px-5 rounded-xl bg-accent-400 hover:bg-accent-300 text-ink-900 text-xs font-semibold disabled:opacity-50"
                        >
                          {committing ? "Importing…" : `Import ${preview.valid_rows} rows`}
                        </button>
                      </div>
                    </motion.div>
                  )}

                  {step === 3 && done && (
                    <motion.div key="done" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="py-10 text-center">
                      <motion.span
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 300, damping: 18 }}
                        className="w-14 h-14 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center"
                      >
                        <CheckCircle2 className="w-7 h-7" />
                      </motion.span>
                      <p className="mt-4 text-base font-semibold text-ink-900">Import complete</p>
                      <p className="mt-1 text-sm text-slate-500">
                        {done.valid_rows} rows imported from {done.filename}
                        {done.skipped_rows ? `, ${done.skipped_rows} skipped` : ""}.
                      </p>
                      <button onClick={() => setDone(null)} className="mt-5 h-10 px-4 rounded-xl bg-brand-700 text-white text-xs font-semibold">
                        Import another file
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </div>
          </Card>

          <Card>
            <SectionTitle title="File format" hint="Column names are matched case-insensitively" />
            <ul className="space-y-2.5">
              {COLUMNS.map(([col, req, note]) => (
                <li key={col} className="flex items-start justify-between gap-3 text-xs">
                  <span>
                    <span className="block font-mono font-semibold text-ink-900">{col}</span>
                    <span className="block text-slate-500">{note}</span>
                  </span>
                  <Badge size="sm" variant={req === "Required" ? "brand" : req === "If paid" ? "warning" : "neutral"}>
                    {req}
                  </Badge>
                </li>
              ))}
            </ul>
            <p className="mt-4 pt-4 border-t border-border-light text-[11px] text-slate-500">
              Re-importing the exact same file is rejected, and existing invoice numbers are never overwritten.
            </p>
          </Card>
        </div>

        <Card className="!p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-border-light flex items-center gap-2">
            <History className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-ink-900">Import history</h3>
          </div>
          <div className="overflow-x-auto">
            <table className={tbl.table}>
              <thead className={tbl.thead}>
                <tr>
                  <th className={tbl.th}>File</th>
                  <th className={tbl.th}>Status</th>
                  <th className={`${tbl.th} text-right`}>Rows</th>
                  <th className={`${tbl.th} text-right`}>Imported</th>
                  <th className={`${tbl.th} text-right`}>Skipped</th>
                  <th className={tbl.th}>When</th>
                </tr>
              </thead>
              <tbody>
                {jobsLoading ? (
                  <SkeletonRows rows={3} cols={6} />
                ) : jobs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-sm text-slate-500">
                      No imports yet.
                    </td>
                  </tr>
                ) : (
                  jobs.map((j) => (
                    <tr key={j.id} className={tbl.tr}>
                      <td className={tbl.td}>
                        <span className="flex items-center gap-2 text-xs font-semibold text-ink-900">
                          <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> {j.filename}
                        </span>
                      </td>
                      <td className={tbl.td}>
                        <Badge size="sm" dot variant={j.status === "completed" ? "success" : j.status === "failed" ? "danger" : "warning"}>
                          {j.status}
                        </Badge>
                      </td>
                      <td className={`${tbl.td} text-right font-mono tabular text-xs`}>{j.total_rows}</td>
                      <td className={`${tbl.td} text-right font-mono tabular text-xs text-emerald-700`}>{j.valid_rows}</td>
                      <td className={`${tbl.td} text-right font-mono tabular text-xs text-slate-500`}>{j.skipped_rows}</td>
                      <td className={`${tbl.td} text-xs text-slate-500 whitespace-nowrap`}>{formatDate(j.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </PageBody>
    </div>
  );
}
