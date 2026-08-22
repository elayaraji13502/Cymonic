import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Target, Flame, ArrowRight, BrainCircuit } from 'lucide-react';
import { studentService, authService } from '../../services/api';
import type { StudentProgress } from '../../types';

const StudentDashboard = () => {
  const [progress, setProgress] = useState<StudentProgress | null>(null);
  const user = authService.getCurrentUser();

  useEffect(() => {
    if (user) {
      studentService.getProgress(user.id).then(res => setProgress(res.data));
    }
  }, [user]);

  if (!progress) return <div>Loading...</div>;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Welcome back, {user?.name} 👋</h1>
        <p className="text-gray-500 mt-1">Let's keep your learning momentum going.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center">
              <Target className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Course Progress</p>
              <h3 className="text-2xl font-bold text-gray-900">{progress.completion}%</h3>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 text-green-600 rounded-lg flex items-center justify-center">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Average Score</p>
              <h3 className="text-2xl font-bold text-gray-900">{progress.averageScore}%</h3>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-orange-100 text-orange-600 rounded-lg flex items-center justify-center">
              <Flame className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Learning Streak</p>
              <h3 className="text-2xl font-bold text-gray-900">{progress.learningStreak} days</h3>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Current Learning Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Current Module</h2>
          </div>
          <div className="p-6 flex-1 flex flex-col justify-between">
            <div>
              <p className="text-sm text-blue-600 font-semibold mb-1">{progress.course}</p>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">{progress.currentModule}</h3>
              <div className="w-full bg-gray-100 rounded-full h-2.5 mb-2">
                <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: '72%' }}></div>
              </div>
              <p className="text-sm text-gray-500 text-right">72% completed</p>
            </div>
            <button className="mt-6 w-full py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors">
              Continue Learning
            </button>
          </div>
        </div>

        {/* AI Coach Card */}
        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl shadow-lg overflow-hidden flex flex-col text-white relative">
          <div className="absolute top-0 right-0 p-6 opacity-10">
            <BrainCircuit className="w-32 h-32" />
          </div>
          <div className="p-6 border-b border-slate-700/50 relative z-10">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <BrainCircuit className="w-5 h-5 text-blue-400" />
              AI Learning Coach
            </h2>
          </div>
          <div className="p-6 flex-1 flex flex-col justify-between relative z-10">
            <div>
              <p className="text-sm text-slate-400 font-medium uppercase tracking-wider mb-2">Current Recommendation</p>
              <div className="inline-block px-4 py-1.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg font-bold tracking-wider mb-4">
                {progress.aiRecommendation?.decision.toUpperCase()}
              </div>
              <p className="text-slate-300 text-lg leading-relaxed">
                "{progress.aiRecommendation?.reasoning}"
              </p>
            </div>
            <Link 
              to="/student/coach"
              className="mt-6 w-full py-3 bg-white/10 hover:bg-white/20 text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
            >
              View AI Reasoning <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentDashboard;
