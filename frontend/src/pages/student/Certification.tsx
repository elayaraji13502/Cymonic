import { Award, CheckCircle2, Circle } from 'lucide-react';

const StudentCertification = () => {
  const requirements = [
    { id: 1, title: 'Complete all 8 modules', status: 'pending', progress: '5/8' },
    { id: 2, title: 'Pass Mid-term Assessment', status: 'completed', progress: 'Passed' },
    { id: 3, title: 'Pass Final Assessment', status: 'pending', progress: 'Not Started' },
    { id: 4, title: 'Complete Capstone Project', status: 'pending', progress: 'Not Started' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Certification Status</h1>
        <p className="text-gray-500 mt-1">Track your progress towards the Python Foundations certificate.</p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="p-8 border-b border-gray-100 flex flex-col md:flex-row items-center gap-8">
          <div className="relative w-48 h-48 flex items-center justify-center shrink-0">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#f1f5f9" strokeWidth="10" />
              <circle 
                cx="50" cy="50" r="45" fill="none" stroke="#2563EB" strokeWidth="10" 
                strokeDasharray="283" strokeDashoffset="170" 
                className="transition-all duration-1000 ease-out"
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <span className="text-4xl font-black text-gray-900">40%</span>
              <span className="text-sm text-gray-500 font-medium">Complete</span>
            </div>
          </div>
          
          <div className="flex-1 text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-bold uppercase tracking-wider mb-4">
              Not Eligible Yet
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Python Foundations Certificate</h2>
            <p className="text-gray-600">
              You are making good progress! Complete the remaining requirements to unlock your verified certificate.
            </p>
          </div>
        </div>

        <div className="p-8 bg-gray-50/50">
          <h3 className="text-lg font-bold text-gray-900 mb-6">Requirements Checklist</h3>
          <div className="space-y-4">
            {requirements.map(req => (
              <div key={req.id} className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-100 shadow-sm">
                <div className="flex items-center gap-4">
                  {req.status === 'completed' ? (
                    <CheckCircle2 className="w-6 h-6 text-green-500 shrink-0" />
                  ) : (
                    <Circle className="w-6 h-6 text-gray-300 shrink-0" />
                  )}
                  <span className={`font-medium ${req.status === 'completed' ? 'text-gray-900' : 'text-gray-600'}`}>
                    {req.title}
                  </span>
                </div>
                <span className={`text-sm font-bold ${req.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                  {req.progress}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentCertification;
