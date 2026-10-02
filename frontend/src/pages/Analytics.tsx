import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

export function Analytics() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["statistics"],
    queryFn: api.getStatistics
  });

  if (isLoading) return <div className="p-8 text-center">Loading analytics...</div>;
  if (error || !stats) return <div className="p-8 text-center text-red-500">Failed to load analytics.</div>;

  const totalPredicted = stats.total_predictions || 1; // avoid div by 0
  const spamPct = Math.round((stats.spam_predictions / totalPredicted) * 100);
  const hamPct = Math.round((stats.ham_predictions / totalPredicted) * 100);

  const observed = stats.user_feedback_observed_outcomes;
  const totalFeedback = stats.total_feedback || 1;
  const fpPct = Math.round((observed.false_positives / totalFeedback) * 100);
  const fnPct = Math.round((observed.false_negatives / totalFeedback) * 100);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold mb-6">Analytics & Metrics</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h2 className="text-lg font-semibold mb-4 text-slate-800 border-b border-slate-100 pb-2">
            Spam vs Ham Distribution
          </h2>
          <div className="space-y-4 mt-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium">SPAM ({stats.spam_predictions})</span>
                <span className="text-slate-500">{spamPct}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div className="bg-red-500 h-2 rounded-full" style={{ width: `${spamPct}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium">HAM ({stats.ham_predictions})</span>
                <span className="text-slate-500">{hamPct}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full" style={{ width: `${hamPct}%` }}></div>
              </div>
            </div>
            <p className="text-xs text-slate-400 mt-4 pt-4 border-t border-slate-50">
              Distribution of {stats.total_predictions} processed emails.
            </p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h2 className="text-lg font-semibold mb-4 text-slate-800 border-b border-slate-100 pb-2 flex justify-between">
            <span>User Observed Feedback Outcomes</span>
            <span className="text-sm font-normal text-slate-500 bg-slate-100 px-2 py-0.5 rounded">Not Model Holdout Metrics</span>
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-50 p-4 rounded-lg">
              <p className="text-xs text-slate-500 font-medium">True Positives (Confirmed Spam)</p>
              <p className="text-xl font-bold mt-1">{observed.true_positives}</p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg">
              <p className="text-xs text-slate-500 font-medium">True Negatives (Confirmed Ham)</p>
              <p className="text-xl font-bold mt-1">{observed.true_negatives}</p>
            </div>
            <div className="bg-red-50 border border-red-100 p-4 rounded-lg">
              <p className="text-xs text-red-600 font-medium">False Positives (Ham marked Spam)</p>
              <p className="text-xl font-bold mt-1 text-red-700">{observed.false_positives}</p>
              <p className="text-xs text-red-500 mt-1">{fpPct}% of feedback</p>
            </div>
            <div className="bg-orange-50 border border-orange-100 p-4 rounded-lg">
              <p className="text-xs text-orange-600 font-medium">False Negatives (Spam marked Ham)</p>
              <p className="text-xl font-bold mt-1 text-orange-700">{observed.false_negatives}</p>
              <p className="text-xs text-orange-500 mt-1">{fnPct}% of feedback</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
