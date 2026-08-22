import { AlertTriangle } from 'lucide-react';

const MentorAtRisk = () => {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">At-Risk Students</h1>
        <p className="text-gray-500 mt-1">Students identified by AI as needing immediate intervention.</p>
      </div>

      <div className="bg-red-50 border border-red-100 rounded-xl p-8 text-center">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-red-900 mb-2">2 Students At Risk</h2>
        <p className="text-red-700 max-w-md mx-auto">
          These students have shown repeated failures or declining engagement. Please review their profiles and schedule a check-in.
        </p>
      </div>
      
      {/* Reusing the table structure from Students.tsx would go here in a real app */}
      <p className="text-center text-gray-500 mt-8">Select a student from the Dashboard or Students list to view details.</p>
    </div>
  );
};

export default MentorAtRisk;
