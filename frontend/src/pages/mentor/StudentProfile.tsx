import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { BrainCircuit, Target, Activity, CheckCircle2 } from 'lucide-react';
import { studentService } from '../../services/api';
import type { StudentProgress } from '../../types';
import { toast } from 'sonner';

const StudentProfile = () => {
  const { studentId } = useParams();
  const [progress, setProgress] = useState<StudentProgress | null>(null);

  useEffect(() => {
    if (studentId) {
      studentService.getProgress(Number(studentId)).then(res => setProgress(res.data));
    }
  }, [studentId]);

  if (!progress) return <div>Loading Student Profile...</div>;

  const { context, aiRecommendation: reasoning } = progress;

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Student Profile</h1>
          <p className="text-gray-500 mt-1">{progress.course} • {progress.currentModule}</p>
        </div>
        <button 
          onClick={() => toast.success('Mentorship session scheduled!')}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
        >
          Schedule Session
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Context */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-gray-500" />
              Performance Metrics
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Latest Score</span>
                <span className="font-semibold">{context.latest_score}%</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Trend</span>
                <span className="capitalize font-medium text-red-600">{context.trend}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Mastery</span>
                <span className="capitalize font-medium text-red-600">{context.mastery.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-500">Engagement</span>
                <span className="capitalize font-medium text-amber-600">{context.engagement}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Middle & Right Column: AI Reasoning for Mentor */}
        <div className="lg:col-span-2 space-y-6">
          {reasoning && (
            <div className="bg-red-50 border border-red-100 p-8 rounded-2xl shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-red-900 flex items-center gap-3">
                  <BrainCircuit className="w-8 h-8 text-red-600" />
                  AI Recommendation: {reasoning.decision.toUpperCase()}
                </h2>
                <div className="flex flex-col items-end">
                  <span className="text-red-700 text-sm uppercase tracking-wider font-semibold">Confidence</span>
                  <span className="text-3xl font-bold text-red-900">{Math.round(reasoning.confidence * 100)}%</span>
                </div>
              </div>
              
              <div className="bg-white p-6 rounded-xl border border-red-100 mb-6">
                <p className="text-lg text-gray-800 font-medium">
                  "{reasoning.reasoning}"
                </p>
              </div>

              <div>
                <h4 className="text-sm font-bold text-red-800 uppercase tracking-wider mb-3">Signals Detected</h4>
                <div className="flex flex-wrap gap-2">
                  {reasoning.signals.map((signal: string) => (
                    <span key={signal} className="px-3 py-1.5 bg-red-100 text-red-800 rounded-lg text-sm font-medium capitalize">
                      {signal.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StudentProfile;
