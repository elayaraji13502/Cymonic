import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Users, AlertTriangle, UserCheck, Award, ArrowRight, BrainCircuit } from 'lucide-react';
import { mentorService, authService } from '../../services/api';
import type { MentorshipRequest } from '../../types';

const MentorDashboard = () => {
  const [stats, setStats] = useState<any>(null);
  const [requests, setRequests] = useState<MentorshipRequest[]>([]);
  const user = authService.getCurrentUser();

  useEffect(() => {
    mentorService.getDashboardStats().then(res => setStats(res.data));
    mentorService.getMentorshipRequests().then(res => setRequests(res.data));
  }, []);

  if (!stats) return <div>Loading...</div>;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Good morning, {user?.name}</h1>
        <p className="text-gray-500 mt-1">Here's how your learners are progressing.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Total Students</p>
              <h3 className="text-2xl font-bold text-gray-900">{stats.totalStudents}</h3>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-red-100 text-red-600 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Need Attention</p>
              <h3 className="text-2xl font-bold text-gray-900">{stats.needsAttention}</h3>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-amber-100 text-amber-600 rounded-lg flex items-center justify-center">
              <UserCheck className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Pending Requests</p>
              <h3 className="text-2xl font-bold text-gray-900">{stats.pendingRequests}</h3>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 text-green-600 rounded-lg flex items-center justify-center">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Cert Ready</p>
              <h3 className="text-2xl font-bold text-gray-900">{stats.certReady}</h3>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-red-50/50">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-red-600" />
            AI Detected Mentorship Needs
          </h2>
        </div>
        <div className="divide-y divide-gray-50">
          {requests.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No pending mentorship requests.</div>
          ) : (
            requests.map(req => (
              <div key={req.id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center font-bold text-red-700 shrink-0">
                    {req.studentName.charAt(0)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-bold text-gray-900">{req.studentName}</h4>
                      <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs font-bold rounded uppercase">
                        {req.priority} Priority
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 font-medium">{req.course} • {req.module}</p>
                    <p className="text-sm text-gray-500 mt-2 italic">"{req.message}"</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-3 shrink-0">
                  <div className="text-right">
                    <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">AI Confidence</p>
                    <p className="font-bold text-lg text-gray-900">{Math.round(req.aiConfidence * 100)}%</p>
                  </div>
                  <Link 
                    to={`/mentor/students/${req.studentId}`}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
                  >
                    View Student Profile <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default MentorDashboard;
