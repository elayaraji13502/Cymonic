import { Outlet, NavLink } from 'react-router-dom';
import { Home, Users, BarChart2, BrainCircuit, Map, UserCheck, Award, History } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { path: '/', icon: Home, label: 'Dashboard' },
    { path: '/learners', icon: Users, label: 'Learners' },
    { path: '/performance/1/3', icon: BarChart2, label: 'Performance' },
    { path: '/reasoning/1/3', icon: BrainCircuit, label: 'AI Reasoning' },
    { path: '/learning-path/1', icon: Map, label: 'Learning Path' },
    { path: '/mentor', icon: UserCheck, label: 'Mentor Check-ins' },
    { path: '/certification/1/10', icon: Award, label: 'Certification' },
    { path: '/history/1', icon: History, label: 'History' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 h-screen sticky top-0 flex flex-col">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <BrainCircuit className="text-white w-5 h-5" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">CYMONIC</h1>
      </div>
      <nav className="flex-1 px-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

const Layout = () => {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 flex flex-col">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
          <h2 className="text-lg font-semibold text-gray-800">Adaptive Learning Coach</h2>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-500">Demo Mode Active</div>
            <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-600 font-medium">
              JD
            </div>
          </div>
        </header>
        <div className="p-8 flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
