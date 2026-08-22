import { UserCheck } from 'lucide-react';

const MentorQueue = () => {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Mentorship Queue</h1>
        <p className="text-gray-500 mt-1">Manage pending mentorship requests and scheduled sessions.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <UserCheck className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Queue is Empty</h2>
        <p className="text-gray-500 max-w-md mx-auto">
          There are no pending mentorship requests at this time. Check the Dashboard for AI-detected needs.
        </p>
      </div>
    </div>
  );
};

export default MentorQueue;
