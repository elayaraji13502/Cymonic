import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { Home, BookOpen, BarChart2, BrainCircuit, Award, History, LogOut } from 'lucide-react';
import { authService } from '../../../services/api';

const StudentLayout = () => {
  const navigate = useNavigate();
  const user = authService.getCurrentUser();

  const navItems = [
    { path: '/student/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/student/courses', icon: BookOpen, label: 'My Courses' },
    { path: '/student/progress', icon: BarChart2, label: 'My Progress' },
    { path: '/student/coach', icon: BrainCircuit, label: 'AI Coach' },
    { path: '/student/certification', icon: Award, label: 'Certification' },
    { path: '/student/history', icon: History, label: 'Decision History' },
  ];

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
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
        <div className="p-4 border-t border-gray-100">
          <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 w-full text-gray-600 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors">
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
          <h2 className="text-lg font-semibold text-gray-800">Student Portal</h2>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-500">Demo Mode Active</div>
            <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center font-bold">
              {user?.name.charAt(0) || 'S'}
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

export default StudentLayout;
