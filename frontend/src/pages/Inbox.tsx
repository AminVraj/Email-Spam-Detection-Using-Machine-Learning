import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { clsx } from "clsx";

export function Inbox() {
  const [filter, setFilter] = useState<"ALL" | "SPAM" | "HAM">("ALL");
  const [selectedEmailId, setSelectedEmailId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["emails"],
    queryFn: api.getEmails
  });

  const emails = data?.emails || [];
  const filteredEmails = emails.filter(e => filter === "ALL" || e.classification === filter);

  if (isLoading) return <div className="flex justify-center p-8">Loading emails...</div>;
  if (error) return <div className="text-red-500 p-8">Failed to load emails.</div>;

  return (
    <div className="flex gap-6 h-[calc(100vh-8rem)]">
      {/* Email List */}
      <div className="w-1/2 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <h2 className="font-semibold">Inbox</h2>
          <div className="flex gap-2">
            {(["ALL", "SPAM", "HAM"] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={clsx(
                  "px-3 py-1 rounded-md text-sm font-medium transition-colors",
                  filter === f 
                    ? "bg-indigo-600 text-white" 
                    : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        
        <div className="flex-1 overflow-auto">
          {filteredEmails.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              No processed emails yet. Sync Gmail to begin.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {filteredEmails.map(email => (
                <li 
                  key={email.id}
                  onClick={() => setSelectedEmailId(email.id)}
                  className={clsx(
                    "p-4 cursor-pointer hover:bg-slate-50 transition-colors",
                    selectedEmailId === email.id && "bg-indigo-50/50"
                  )}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium truncate max-w-[200px]">{email.sender}</span>
                    <span className="text-xs text-slate-400">
                      {new Date(email.received_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="text-sm font-medium text-slate-800 truncate mb-2">
                    {email.subject || "(No Subject)"}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={clsx(
                      "text-xs px-2 py-0.5 rounded font-medium",
                      email.classification === "SPAM" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                    )}>
                      {email.classification}
                    </span>
                    <span className="text-xs text-slate-500 border border-slate-200 px-2 py-0.5 rounded">
                      Model: {email.model_version}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Email Detail Panel */}
      <div className="w-1/2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
        {selectedEmailId ? (
          <EmailDetail emailId={selectedEmailId} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 p-8 text-center">
            Select an email to view details and provide feedback.
          </div>
        )}
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
      <div className="p-6 border-b border-slate-100 bg-slate-50">
        <h2 className="text-xl font-bold mb-4">{email.subject || "(No Subject)"}</h2>
        <div className="space-y-2 text-sm">
          <div className="flex items-start">
            <span className="text-slate-500 w-24">From:</span>
            <span className="font-medium">{email.sender}</span>
          </div>
          <div className="flex items-start">
            <span className="text-slate-500 w-24">Received:</span>
            <span>{new Date(email.received_at).toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-4 mt-2">
            <div className="flex items-center gap-2">
              <span className="text-slate-500">Classification:</span>
              <span className={clsx(
                "px-2 py-0.5 rounded text-xs font-bold",
                email.classification === "SPAM" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
              )}>
                {email.classification}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500">Decision Score:</span>
              <span className="font-mono text-xs bg-slate-200 px-2 py-0.5 rounded">
                {email.decision_score.toFixed(4)}
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-6 whitespace-pre-wrap font-mono text-sm text-slate-700 bg-white">
        {email.body || "(Empty Body)"}
      </div>

      <div className="p-4 border-t border-slate-200 bg-slate-50">
        <h3 className="font-medium mb-3 text-sm">Provide Validation Feedback</h3>
        <p className="text-xs text-slate-500 mb-4">
          User feedback is used as validated training data for future candidate models. 
          It does not instantly change the current production model.
        </p>
        
        {email.feedback ? (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between">
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
