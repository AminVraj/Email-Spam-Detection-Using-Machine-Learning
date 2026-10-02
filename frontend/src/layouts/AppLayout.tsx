import { Outlet, NavLink } from "react-router-dom";
import { 
  LayoutDashboard, 
  Inbox, 
  BarChart2, 
  Brain, 
  Settings, 
  Shield,
  FileSearch
} from "lucide-react";
import { clsx } from "clsx";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Inbox", href: "/inbox", icon: Inbox },
  { name: "Analyze Email", href: "/analyze", icon: FileSearch },
  { name: "Analytics", href: "/analytics", icon: BarChart2 },
  { name: "Adaptive Learning", href: "/adaptive", icon: Brain },
  { name: "Model Management", href: "/models", icon: Shield },
];

export function AppLayout() {
  return (
    <div className="flex h-screen bg-slate-50 text-slate-900">
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-6 flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white">
            <Shield size={24} />
          </div>
          <h1 className="font-bold text-lg leading-tight">Spam Shield<br/><span className="text-sm font-normal text-slate-500">Adaptive Engine</span></h1>
        </div>
        
        <nav className="flex-1 px-4 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  isActive
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
                )
              }
            >
              <item.icon size={20} />
              {item.name}
            </NavLink>
          ))}
        </nav>
        
        <div className="p-4 border-t border-slate-200 text-xs text-slate-500">
          <p>Phase 6 MVP</p>
          <p className="mt-1 flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500"></span> System Online</p>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center px-8 justify-between shrink-0">
          <h2 className="font-semibold text-xl">Admin Console</h2>
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600">
              <Settings size={18} />
            </div>
          </div>
        </header>
        <div className="flex-1 overflow-auto p-8">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
