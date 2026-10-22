import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { clsx } from "clsx";
import { Search, Mail, ShieldAlert, ShieldCheck, Tag } from "lucide-react";

export function Inbox() {
  const [filter, setFilter] = useState<"ALL" | "SPAM" | "HAM" | "PROMOTION">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEmailId, setSelectedEmailId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["emails"],
    queryFn: api.getEmails,
    refetchOnWindowFocus: true,
  });

  const emails = data?.emails || [];

  const totalCount = emails.length;
  const spamCount = emails.filter((e) => e.classification === "SPAM").length;
  const hamCount = emails.filter((e) => e.classification === "HAM").length;
  const promoCount = emails.filter((e) => e.classification === "PROMOTION" || e.provider_category === "PROMOTIONS").length;

  const filteredEmails = emails.filter((e) => {
    const matchesFilter = filter === "ALL" || e.classification === filter;
    const matchesSearch =
      !searchQuery ||
      (e.subject && e.subject.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (e.sender && e.sender.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  if (isLoading) return <div className="flex justify-center p-8">Loading emails...</div>;
  if (error) return <div className="text-red-500 p-8">Failed to load emails.</div>;

  return (
    <div className="space-y-4 h-[calc(100vh-8rem)] flex flex-col">
      {/* Top summary stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-3">
          <div className="bg-blue-50 dark:bg-blue-900/30 p-2.5 rounded-lg">
            <Mail className="text-blue-600 dark:text-blue-400" size={20} />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Total Emails Analyzed</p>
            <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{totalCount}</p>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-3">
          <div className="bg-red-50 dark:bg-red-900/30 p-2.5 rounded-lg">
            <ShieldAlert className="text-red-600 dark:text-red-400" size={20} />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Total Spam Emails</p>
            <p className="text-xl font-bold text-red-600 dark:text-red-400">{spamCount}</p>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-3">
          <div className="bg-green-50 dark:bg-green-900/30 p-2.5 rounded-lg">
            <ShieldCheck className="text-green-600 dark:text-green-400" size={20} />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Total Ham Emails</p>
            <p className="text-xl font-bold text-green-600 dark:text-green-400">{hamCount}</p>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex items-center gap-3">
          <div className="bg-orange-50 dark:bg-orange-900/30 p-2.5 rounded-lg">
            <Tag className="text-orange-600 dark:text-orange-400" size={20} />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Promotions</p>
            <p className="text-xl font-bold text-orange-600 dark:text-orange-400">{promoCount}</p>
          </div>
        </div>
      </div>

      {/* Inbox split view */}
      <div className="flex gap-6 flex-1 min-h-0">
        {/* Email List */}
        <div className="w-1/2 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-200 dark:border-slate-700 space-y-3 bg-slate-50 dark:bg-slate-900">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search subject or sender..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-1.5 text-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-sm text-slate-700 dark:text-slate-200">Inbox</h2>
              <div className="flex gap-1.5">
                {(["ALL", "SPAM", "HAM", "PROMOTION"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={clsx(
                      "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
                      filter === f
                        ? "bg-indigo-600 text-white"
                        : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700"
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-auto divide-y divide-slate-100 dark:divide-slate-700/50">
            {filteredEmails.length === 0 ? (
              <div className="p-8 text-center text-slate-500 dark:text-slate-400 text-sm">
                No matching emails found.
              </div>
            ) : (
              filteredEmails.map((email) => (
                <div
                  key={email.id}
                  onClick={() => setSelectedEmailId(email.id)}
                  className={clsx(
                    "p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors",
                    selectedEmailId === email.id && "bg-indigo-50 dark:bg-indigo-900/30"
                  )}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-sm truncate max-w-[220px] text-slate-800 dark:text-slate-100">
                      {email.sender || "(Unknown Sender)"}
                    </span>
                    <span className="text-xs text-slate-400">
                      {email.received_at ? new Date(email.received_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate mb-2">
                    {email.subject || "(No Subject)"}
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded font-semibold",
                        email.classification === "SPAM"
                          ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border border-red-200 dark:border-red-800"
                          : email.classification === "PROMOTION"
                          ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400 border border-orange-200 dark:border-orange-800"
                          : "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 border border-green-200 dark:border-green-800"
                      )}
                    >
                      {email.classification}
                    </span>
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 font-mono text-[11px]">
                      {email.decision_score !== undefined && email.decision_score !== null && (
                        <span>Score: {Number(email.decision_score).toFixed(3)}</span>
                      )}
                      <span className="border border-slate-200 dark:border-slate-700 px-1.5 py-0.5 rounded">
                        {email.model_version}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Email Detail Panel */}
        <div className="w-1/2 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden flex flex-col">
          {selectedEmailId ? (
            <EmailDetail emailId={selectedEmailId} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-500 dark:text-slate-400 p-8 text-center text-sm">
              Select an email from the list to view its details and prediction scores.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EmailDetail({ emailId }: { emailId: number }) {
  const queryClient = useQueryClient();
  const { data: email, isLoading, error } = useQuery({
    queryKey: ["email", emailId],
    queryFn: () => api.getEmailDetails(emailId)
  });

  const feedbackMutation = useMutation({
    mutationFn: (label: "SPAM" | "HAM") => api.submitFeedback(emailId, label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["email", emailId] });
      queryClient.invalidateQueries({ queryKey: ["statistics"] });
      queryClient.invalidateQueries({ queryKey: ["feedback-quality"] });
    }
  });

  if (isLoading) return <div className="p-8 text-center">Loading details...</div>;
  if (error || !email) return <div className="p-8 text-center text-red-500">Failed to load email details.</div>;

  return (
    <>
      <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
        <h2 className="text-xl font-bold mb-4">{email.subject || "(No Subject)"}</h2>
        <div className="space-y-2 text-sm">
          <div className="flex items-start">
            <span className="text-slate-500 dark:text-slate-400 w-24">From:</span>
            <span className="font-medium">{email.sender}</span>
          </div>
          <div className="flex items-start">
            <span className="text-slate-500 dark:text-slate-400 w-24">Received:</span>
            <span>{email.received_at ? new Date(email.received_at).toLocaleString() : "N/A"}</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 mt-2">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400">Classification:</span>
              <span className={clsx(
                "px-2 py-0.5 rounded text-xs font-bold border",
                email.classification === "SPAM" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-red-200 dark:border-red-800" :
                email.classification === "PROMOTION" ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400 border-orange-200 dark:border-orange-800" :
                "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 border-green-200 dark:border-green-800"
              )}>
                {email.classification}
              </span>
            </div>
            {email.classification === "PROMOTION" && email.ml_prediction && (
              <div className="flex items-center gap-2">
                <span className="text-slate-500 dark:text-slate-400">Underlying ML:</span>
                <span className={clsx(
                  "font-mono text-xs px-2 py-0.5 rounded border font-semibold",
                  email.ml_prediction === "SPAM" ? "bg-red-50 text-red-600 dark:bg-red-900/20 border-red-300" : "bg-green-50 text-green-600 dark:bg-green-900/20 border-green-300"
                )}>
                  {email.ml_prediction}
                </span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400">Category:</span>
              <span className="font-mono text-xs bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600">
                {email.provider_category || "PRIMARY"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400">Decision Score:</span>
              <span className="font-mono text-xs bg-slate-200 dark:bg-slate-700 px-2 py-0.5 rounded">
                {email.decision_score !== undefined && email.decision_score !== null ? Number(email.decision_score).toFixed(4) : "N/A"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400">Model:</span>
              <span className="font-mono text-xs border border-slate-200 dark:border-slate-700 px-2 py-0.5 rounded">
                {email.model_version}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 whitespace-pre-wrap font-mono text-sm text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800">
        {email.body || "(Empty Body)"}
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">
        <h3 className="font-medium mb-3 text-sm">Provide Validation Feedback</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          User feedback is used as validated training data for future candidate models.
          It does not instantly change the current production model.
        </p>

        {email.feedback ? (
          <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 text-green-700 dark:text-green-400 px-4 py-3 rounded-lg text-sm flex items-center justify-between">
            <span>Feedback recorded: Marked as <strong>{email.feedback.user_label}</strong></span>
          </div>
        ) : (
          <div className="flex gap-3">
            <button
              onClick={() => feedbackMutation.mutate("SPAM")}
              disabled={feedbackMutation.isPending}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {email.classification === "SPAM" ? "Confirm SPAM" : "Mark as SPAM"}
            </button>
            <button
              onClick={() => feedbackMutation.mutate("HAM")}
              disabled={feedbackMutation.isPending}
              className="flex-1 bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {email.classification === "HAM" ? "Confirm HAM" : "Mark as HAM"}
            </button>
          </div>
        )}

        {feedbackMutation.isError && (
          <div className="mt-3 text-red-500 text-sm">
            {feedbackMutation.error.message}
          </div>
        )}
      </div>
    </>
  );
}
