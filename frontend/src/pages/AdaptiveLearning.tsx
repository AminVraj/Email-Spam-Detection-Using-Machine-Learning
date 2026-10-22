import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { Brain, CheckCircle2, AlertCircle, ArrowDown } from "lucide-react";
import { clsx } from "clsx";

export function AdaptiveLearning() {
  const { data: report, isLoading, error } = useQuery({
    queryKey: ["feedback-quality"],
    queryFn: api.getFeedbackQuality
  });

  if (isLoading) return <div className="p-8 text-center">Loading feedback report...</div>;
  if (error || !report) return <div className="p-8 text-center text-red-500">Failed to load feedback report.</div>;

  const pct = Math.min(100, Math.round((report.valid_feedback / report.minimum_required) * 100));

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <div className="bg-purple-100 p-3 rounded-lg text-purple-600">
          <Brain size={28} />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Adaptive Learning</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">Automated feedback processing and candidate training</p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-8">
        <h2 className="text-lg font-semibold mb-6">Training Readiness Status</h2>
        
        <div className="flex items-center justify-between mb-2">
          <span className="font-medium">
            {report.valid_feedback} / {report.minimum_required} validated feedback samples
          </span>
          <span className={clsx(
            "px-3 py-1 rounded-full text-sm font-bold flex items-center gap-2",
            report.training_ready ? "bg-green-100 text-green-700 dark:text-green-400" : "bg-amber-100 text-amber-700"
          )}>
            {report.training_ready ? <CheckCircle2 size={16}/> : <AlertCircle size={16}/>}
            {report.training_ready ? "Ready for candidate training" : "Not Ready"}
          </span>
        </div>
        
        <div className="w-full bg-slate-100 rounded-full h-4 mb-8">
          <div 
            className={clsx(
              "h-4 rounded-full transition-all duration-1000",
              report.training_ready ? "bg-green-500" : "bg-amber-500"
            )}
            style={{ width: `${pct}%` }}
          ></div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 border-t border-slate-100 dark:border-slate-800">
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Total Feedback</p>
            <p className="text-xl font-bold mt-1">{report.total_feedback}</p>
          </div>
          <div>
            <p className="text-xs text-green-600 font-medium">Valid / Usable</p>
            <p className="text-xl font-bold mt-1 text-green-700 dark:text-green-400">{report.valid_feedback}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Duplicates Deduplicated</p>
            <p className="text-xl font-bold mt-1">{report.duplicate_feedback}</p>
          </div>
          <div>
            <p className="text-xs text-red-600 font-medium">Conflicting / Rejected</p>
            <p className="text-xl font-bold mt-1 text-red-700 dark:text-red-400">{report.conflicting_feedback}</p>
          </div>
        </div>
      </div>

      <div className="bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-8">
        <h3 className="font-bold mb-6 text-center">Controlled Model Evolution Pipeline</h3>
        
        <div className="flex flex-col items-center max-w-sm mx-auto space-y-2">
          <PipelineStep label="1. User Correction" desc="User provides SPAM/HAM feedback" />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="2. Feedback Validation" desc="Deduplication & contradiction checks" />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="3. Validated Feedback" desc="Combined with baseline dataset" />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="4. Training Threshold" desc="Requires minimum samples" highlight={!report.training_ready} />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="5. Candidate Model" desc="Isolated training artifact created" highlight={report.training_ready} />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="6. Model Governance" desc="Strict evaluation against holdout" />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="7. Admin Promotion" desc="Explicit human approval required" />
          <ArrowDown size={20} className="text-slate-400" />
          <PipelineStep label="8. Production Model" desc="Actively serving predictions" final />
        </div>
        
        <div className="mt-8 bg-blue-50 border border-blue-100 p-4 rounded-lg text-sm text-blue-800">
          <strong>Notice:</strong> USER FEEDBACK ≠ AUTOMATIC GROUND TRUTH. Feedback is treated as unverified input until it passes validation. Candidate models are never automatically promoted.
        </div>
      </div>
    </div>
  );
}

function PipelineStep({ label, desc, highlight, final }: { label: string, desc: string, highlight?: boolean, final?: boolean }) {
  return (
    <div className={clsx(
      "w-full p-3 rounded-lg border text-center transition-colors shadow-sm",
      final ? "bg-indigo-600 text-white border-indigo-700 font-bold" : 
      highlight ? "bg-amber-100 border-amber-300 text-amber-900" : "bg-white dark:bg-slate-800 border-slate-300 text-slate-800 dark:text-slate-100"
    )}>
      <div className="text-sm">{label}</div>
      <div className={clsx("text-xs mt-1", final ? "text-indigo-200" : "text-slate-500 dark:text-slate-400")}>{desc}</div>
    </div>
  );
}
