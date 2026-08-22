import { BarChart2 } from 'lucide-react';

const MentorAnalytics = () => {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
        <p className="text-gray-500 mt-1">Cohort-level performance and intervention metrics.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <BarChart2 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Cohort Analytics</h2>
        <p className="text-gray-500 max-w-md mx-auto">
          Detailed charts showing student performance distribution, decision distribution, and course completion rates will appear here.
        </p>
      </div>
    </div>
  );
};

export default MentorAnalytics;
