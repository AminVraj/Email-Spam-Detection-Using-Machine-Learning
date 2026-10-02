import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { clsx } from "clsx";
import { 
  Shield, 
  GitMerge, 
  RotateCcw, 
  Play
} from "lucide-react";

export function ModelManagement() {
  const queryClient = useQueryClient();
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels
  });

  const { data: qualityReport } = useQuery({
    queryKey: ["feedback-quality"],
    queryFn: api.getFeedbackQuality
  });

  const trainMutation = useMutation({
    mutationFn: api.trainCandidate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["feedback-quality"] });
    }
  });

  const models = data?.models || [];
  const prodModel = models.find(m => m.status === "production");

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold">Model Management</h1>
          <p className="text-slate-500 text-sm mt-1">Admin actions for model lifecycle and governance</p>
        </div>
        
        <button
          onClick={() => trainMutation.mutate()}
          disabled={!qualityReport?.training_ready || trainMutation.isPending}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:bg-slate-400 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
        >
          <Play size={18} className={trainMutation.isPending ? "animate-pulse" : ""} />
          {trainMutation.isPending ? "Training in progress..." : "Train Candidate Model"}
        </button>
      </div>

      {!qualityReport?.training_ready && !trainMutation.isPending && qualityReport && (
        <div className="bg-amber-50 text-amber-700 p-4 rounded-lg text-sm border border-amber-200">
          Candidate training is not ready because the required validated feedback threshold has not been reached ({qualityReport.valid_feedback} / {qualityReport.minimum_required}).
        </div>
      )}
      
      {trainMutation.isError && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg text-sm border border-red-200">
          Training failed: {trainMutation.error.message}
        </div>
      )}

      {trainMutation.isSuccess && (
        <div className="bg-green-50 text-green-700 p-4 rounded-lg text-sm border border-green-200">
          Successfully trained candidate model version: {trainMutation.data.version}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
            <tr>
              <th className="px-6 py-4 font-medium">Version</th>
              <th className="px-6 py-4 font-medium">Algorithm</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Training Time</th>
              <th className="px-6 py-4 font-medium">Feedback Used</th>
              <th className="px-6 py-4 font-medium">F1 Score</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {models.map(model => (
              <tr key={model.version} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4 font-medium">
                  {model.version}
                  {model.status === "production" && (
                    <span className="block text-xs font-normal text-indigo-600 mt-0.5">Currently serving predictions</span>
                  )}
                </td>
                <td className="px-6 py-4">{model.algorithm}</td>
                <td className="px-6 py-4">
                  <span className={clsx(
                    "px-2.5 py-1 rounded-full text-xs font-medium border",
                    model.status === "production" ? "bg-indigo-50 text-indigo-700 border-indigo-200" :
                    model.status === "candidate" ? "bg-amber-50 text-amber-700 border-amber-200" :
                    "bg-slate-100 text-slate-600 border-slate-200"
                  )}>
                    {model.status.toUpperCase()}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-500">
                  {new Date(model.training_timestamp).toLocaleString()}
                </td>
                <td className="px-6 py-4">{model.feedback_count_used}</td>
                <td className="px-6 py-4 font-mono bg-slate-50">
                  {model.metrics?.Spam_F1 ? model.metrics.Spam_F1.toFixed(4) : "-"}
                </td>
                <td className="px-6 py-4 text-right">
                  <button
                    onClick={() => setSelectedVersion(selectedVersion === model.version ? null : model.version)}
                    className="text-indigo-600 hover:text-indigo-800 font-medium px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition-colors"
                  >
                    {selectedVersion === model.version ? "Close" : "Manage"}
                  </button>
                </td>
              </tr>
            ))}
            {models.length === 0 && !isLoading && (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                  No models found in the database.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedVersion && (
        <ModelActionsPanel 
          version={selectedVersion} 
          status={models.find(m => m.version === selectedVersion)?.status || ""} 
          prodVersion={prodModel?.version}
        />
      )}
    </div>
  );
}

function ModelActionsPanel({ version, status, prodVersion }: { version: string, status: string, prodVersion?: string }) {
  const queryClient = useQueryClient();
  const [comparing, setComparing] = useState(false);
  
  const { data: comp, isLoading: compLoading, error: compError } = useQuery({
    queryKey: ["compare", version],
    queryFn: () => api.compareModel(version),
    enabled: comparing
  });

  const promoteMutation = useMutation({
    mutationFn: (v: string) => api.promoteModel(v),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["statistics"] });
      setComparing(false);
    }
  });

  const rollbackMutation = useMutation({
    mutationFn: (v: string) => api.rollbackModel(v),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["statistics"] });
    }
  });

  if (status === "production") {
    return (
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6 text-indigo-900">
        <div className="flex items-center gap-2 font-bold mb-2">
          <Shield size={20} /> Production Model ({version})
        </div>
        <p className="text-sm">This is the current active model handling all incoming email predictions.</p>
      </div>
    );
  }

  if (status === "archived") {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="font-bold mb-1">Archived Model ({version})</h3>
            <p className="text-sm text-slate-500">This model was previously in production.</p>
          </div>
          <button
            onClick={() => {
              if(confirm(`Are you sure you want to rollback production to ${version}?`)) {
                rollbackMutation.mutate(version);
              }
            }}
            disabled={rollbackMutation.isPending}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            <RotateCcw size={18} />
            {rollbackMutation.isPending ? "Rolling back..." : "Rollback to this version"}
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-4">
          Rollback changes the production model used for future predictions. It does not retrain the model.
        </p>
        
        {rollbackMutation.isError && (
          <div className="mt-4 text-red-500 text-sm">{rollbackMutation.error.message}</div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="font-bold text-lg">Candidate Model ({version})</h3>
          <p className="text-sm text-slate-500">Compare with production ({prodVersion}) and promote if approved.</p>
        </div>
        
        {!comparing && (
          <button
            onClick={() => setComparing(true)}
            className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 px-4 py-2 rounded-lg font-medium transition-colors"
          >
            <GitMerge size={18} />
            Run Governance Evaluation
          </button>
        )}
      </div>

      {comparing && compLoading && <div className="py-4 text-center">Running governance checks...</div>}
      {comparing && compError && <div className="py-4 text-center text-red-500">Failed to compare model.</div>}
      
      {comparing && comp && (
        <div className="space-y-6 border-t border-slate-100 pt-6">
          <div className="flex items-center gap-3">
            <span className={clsx(
              "px-3 py-1 rounded font-bold text-sm",
              comp.comparison.decision === "APPROVED" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            )}>
              Governance evaluation result: {comp.comparison.decision}
            </span>
            <span className="text-sm text-slate-500">
              Evaluated against holdout dataset.
            </span>
          </div>

          <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
            <h4 className="font-medium mb-3 text-sm border-b border-slate-200 pb-2">Governance Rules Evaluated</h4>
            <ul className="space-y-2 text-sm">
              <li className="flex justify-between">
                <span className="text-slate-600">Spam Precision Degradation &lt; 0.02:</span>
                <span className="font-mono">{comp.comparison.degradation.Spam_Precision.toFixed(4)}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-slate-600">Spam Recall Degradation &lt; 0.05:</span>
                <span className="font-mono">{comp.comparison.degradation.Spam_Recall.toFixed(4)}</span>
              </li>
              <li className="flex justify-between">
                <span className="text-slate-600">False Positive Rate (FPR) &lt; 0.02:</span>
                <span className="font-mono">{comp.comparison.fpr.toFixed(4)}</span>
              </li>
            </ul>
          </div>

          {comp.comparison.reasons && comp.comparison.reasons.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h4 className="font-medium text-red-800 mb-2 text-sm">Rejection Reasons:</h4>
              <ul className="list-disc pl-5 text-sm text-red-700 space-y-1">
                {comp.comparison.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}

          {comp.comparison.decision === "APPROVED" && (
            <div>
              <button
                onClick={() => {
                  if(confirm(`Promote candidate ${version} to production?`)) {
                    promoteMutation.mutate(version);
                  }
                }}
                disabled={promoteMutation.isPending}
                className="w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold transition-colors"
              >
                {promoteMutation.isPending ? "Promoting..." : "Promote to Production"}
              </button>
              {promoteMutation.isError && (
                <div className="mt-2 text-red-500 text-sm text-center">{promoteMutation.error.message}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
