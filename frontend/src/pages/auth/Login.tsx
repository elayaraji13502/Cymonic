import { useNavigate } from 'react-router-dom';
import { BrainCircuit, GraduationCap, UserCheck } from 'lucide-react';
import { authService } from '../../services/api';

const Login = () => {
  const navigate = useNavigate();

  const handleLogin = async (role: 'student' | 'mentor') => {
    await authService.login(role);
    navigate(`/${role}/dashboard`);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center">
        <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg">
          <BrainCircuit className="text-white w-10 h-10" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">CYMONIC</h1>
        <p className="text-gray-500 mt-2">Adaptive Learning Coach</p>
      </div>

      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 w-full max-w-md">
        <h2 className="text-xl font-semibold text-center mb-6">Select Demo Role</h2>
        
        <div className="space-y-4">
          <button
            onClick={() => handleLogin('student')}
            className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-gray-100 hover:border-blue-500 hover:bg-blue-50 transition-all group"
          >
            <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div className="text-left">
              <h3 className="font-bold text-gray-900">Student Portal</h3>
              <p className="text-sm text-gray-500">Experience the AI Coach</p>
            </div>
          </button>

          <button
            onClick={() => handleLogin('mentor')}
            className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-gray-100 hover:border-purple-500 hover:bg-purple-50 transition-all group"
          >
            <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <UserCheck className="w-6 h-6" />
            </div>
            <div className="text-left">
              <h3 className="font-bold text-gray-900">Mentor Portal</h3>
              <p className="text-sm text-gray-500">Manage interventions</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
