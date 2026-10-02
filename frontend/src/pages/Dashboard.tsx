import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { 
  BarChart, 
  Mail, 
  ShieldAlert, 
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
  CheckCircle2
} from "lucide-react";

export function Dashboard() {
  const queryClient = useQueryClient();

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ["statistics"],
    queryFn: api.getStatistics
  });

  const { data: authStatus } = useQuery({
    queryKey: ["gmail-auth"],
    queryFn: api.getGmailAuthStatus
  });

  const syncMutation = useMutation({
    mutationFn: api.syncGmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["statistics"] });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
    }
  });

  if (statsLoading) {
    return <div className="flex h-64 items-center justify-center">Loading dashboard...</div>;
  }

  if (statsError) {
    return (
      <div className="bg-red-50 text-red-600 p-4 rounded-lg">
        Failed to load statistics. Please ensure the backend is running.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">System Overview</h1>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm bg-white px-3 py-1.5 rounded-full shadow-sm border border-slate-200">
            {authStatus?.authenticated ? (
              <><span className="w-2 h-2 rounded-full bg-green-500"></span> Gmail Connected</>
            ) : (
              <><span className="w-2 h-2 rounded-full bg-red-500"></span> Gmail Disconnected</>
            )}
          </div>
          
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending || !authStatus?.authenticated}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            <RefreshCw size={18} className={syncMutation.isPending ? "animate-spin" : ""} />
            {syncMutation.isPending ? "Syncing..." : "Sync Gmail"}
          </button>
        </div>
      </div>

      {syncMutation.isError && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg flex items-center gap-3">
          <AlertTriangle size={20} />
          <span>Failed to sync Gmail. Please check your authentication status or backend logs.</span>
        </div>
      )}

      {syncMutation.isSuccess && (
        <div className="bg-green-50 text-green-700 p-4 rounded-lg flex items-center gap-3">
          <CheckCircle2 size={20} />
          <span>
            Sync complete! Processed {syncMutation.data.messages_processed} emails 
            ({syncMutation.data.new_spam} SPAM, {syncMutation.data.new_ham} HAM).
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Processed" 
          value={stats?.total_predictions} 
          icon={<Mail className="text-blue-500" size={24} />} 
        />
        <StatCard 
          title="Detected Spam" 
          value={stats?.spam_predictions} 
          icon={<ShieldAlert className="text-red-500" size={24} />} 
        />
        <StatCard 
          title="Clean Emails (Ham)" 
          value={stats?.ham_predictions} 
          icon={<ShieldCheck className="text-green-500" size={24} />} 
        />
        <StatCard 
          title="User Corrections" 
          value={stats?.user_corrections} 
          icon={<BarChart className="text-purple-500" size={24} />} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="font-semibold text-lg mb-4">Model Information</h3>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Active Production Model</span>
              <span className="font-medium bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-sm">
                {stats?.model_version}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Observed False Positives</span>
              <span className="font-medium text-red-600">{stats?.user_feedback_observed_outcomes.false_positives}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-500">Observed False Negatives</span>
              <span className="font-medium text-red-600">{stats?.user_feedback_observed_outcomes.false_negatives}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon }: { title: string; value?: number; icon: React.ReactNode }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
      <div className="bg-slate-50 p-3 rounded-lg">
        {icon}
      </div>
      <div>
        <p className="text-sm text-slate-500 font-medium">{title}</p>
        <p className="text-2xl font-bold mt-1">{value !== undefined ? value : "-"}</p>
      </div>
    </div>
  );
}
