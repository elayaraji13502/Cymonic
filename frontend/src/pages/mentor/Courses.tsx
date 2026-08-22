import { BookOpen } from 'lucide-react';

const MentorCourses = () => {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Course Management</h1>
        <p className="text-gray-500 mt-1">Manage course content and view AI improvement insights.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <BookOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Course Editor</h2>
        <p className="text-gray-500 max-w-md mx-auto">
          Select a course to edit modules, add content, or view AI-generated insights on where learners are struggling.
        </p>
      </div>
    </div>
  );
};

export default MentorCourses;
