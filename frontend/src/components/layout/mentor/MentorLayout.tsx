import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { Home, Users, AlertTriangle, BrainCircuit, UserCheck, BookOpen, BarChart2, LogOut } from 'lucide-react';
import { authService } from '../../../services/api';

const MentorLayout = () => {
  const navigate = useNavigate();
  const user = authService.getCurrentUser();

  const navItems = [
    { path: '/mentor/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/mentor/students', icon: Users, label: 'Students' },
    { path: '/mentor/at-risk', icon: AlertTriangle, label: 'At-Risk Students' },
    { path: '/mentor/mentorship', icon: UserCheck, label: 'Mentorship Queue' },
    { path: '/mentor/courses', icon: BookOpen, label: 'Course Management' },
    { path: '/mentor/analytics', icon: BarChart2, label: 'Analytics' },
  ];

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="w-64 bg-gray-900 text-white h-screen sticky top-0 flex flex-col">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
            <BrainCircuit className="text-white w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold">CYMONIC</h1>
        </div>
        <nav className="flex-1 px-4 space-y-1 mt-4">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-purple-600 text-white font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800">
          <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 w-full text-gray-400 hover:bg-red-500/10 hover:text-red-400 rounded-lg transition-colors">
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
          <h2 className="text-lg font-semibold text-gray-800">Mentor Portal</h2>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-500">Demo Mode Active</div>
            <div className="w-8 h-8 bg-purple-100 text-purple-700 rounded-full flex items-center justify-center font-bold">
              {user?.name.charAt(0) || 'M'}
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

export default MentorLayout;
