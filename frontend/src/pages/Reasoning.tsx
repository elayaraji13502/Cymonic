import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BrainCircuit, CheckCircle2, AlertTriangle, XCircle, ArrowRight, Activity, Target, AlertCircle } from 'lucide-react';
import { learnerService } from '../services/api';
import { toast } from 'sonner';

const Reasoning = () => {
  const { learnerId, lessonId } = useParams();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch context and reasoning
        const contextRes = await learnerService.getPerformance(Number(learnerId), Number(lessonId));
        const reasoningRes = await learnerService.evaluateDecision(Number(learnerId), Number(lessonId), contextRes.data);
        
        setData({
          context: contextRes.data,
          reasoning: reasoningRes.data
        });
      } catch (error) {
        toast.error('Failed to load AI reasoning');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [learnerId, lessonId]);

  const handleApply = async () => {
    setApplying(true);
    try {
      await learnerService.applyDecision({
        learner_id: Number(learnerId),
        lesson_id: Number(lessonId),
        ...data.reasoning
      });
      setApplied(true);
      toast.success('Recommendation applied successfully!');
    } catch (error) {
      toast.error('Failed to apply recommendation');
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-4">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
        >
          <BrainCircuit className="w-12 h-12 text-blue-600" />
        </motion.div>
        <p className="text-lg text-gray-600 font-medium">AI is analyzing learner context...</p>
      </div>
    );
  }

  if (!data) return <div>Error loading data</div>;

  const { context, reasoning } = data;

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case 'advance': return 'bg-green-100 text-green-800 border-green-200';
      case 'reinforce': return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'mentor': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Reasoning Engine</h1>
          <p className="text-gray-500 mt-1">Transparent decision making process</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 rounded-full font-medium">
          <BrainCircuit className="w-5 h-5" />
          <span>Source: {reasoning.reasoning_source.toUpperCase()}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Context & Signals */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-gray-500" />
              Learner Context
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Latest Score</span>
                <span className="font-semibold">{context.latest_score}%</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Trend</span>
                <span className="capitalize font-medium text-amber-600">{context.trend}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-gray-50">
                <span className="text-gray-500">Mastery</span>
                <span className="capitalize font-medium text-red-600">{context.mastery.status.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-500">Engagement</span>
                <span className="capitalize font-medium">{context.engagement.status}</span>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-gray-500" />
              Signals Identified
            </h3>
            <div className="flex flex-wrap gap-2">
              {reasoning.signals.map((signal: string) => (
                <span key={signal} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium capitalize">
                  {signal.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Middle & Right Column: Reasoning & Decision */}
        <div className="lg:col-span-2 space-y-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-blue-600 to-indigo-700 p-8 rounded-2xl shadow-lg text-white"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <BrainCircuit className="w-8 h-8" />
                AI Thinking
              </h2>
              <div className="flex flex-col items-end">
                <span className="text-blue-200 text-sm uppercase tracking-wider font-semibold">Confidence</span>
                <span className="text-3xl font-bold">{Math.round(reasoning.confidence * 100)}%</span>
              </div>
            </div>
            <p className="text-lg leading-relaxed text-blue-50">
              "{reasoning.reasoning}"
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(reasoning.rejected_alternatives).map(([strategy, reason]) => {
              if (strategy === reasoning.decision) return null;
              return (
                <div key={strategy} className="bg-white p-5 rounded-xl border border-gray-200 opacity-75">
                  <div className="flex items-center gap-2 mb-2 text-gray-500">
                    <XCircle className="w-5 h-5" />
                    <h4 className="font-semibold capitalize line-through">{strategy}</h4>
                  </div>
                  <p className="text-sm text-gray-600">{reason as string}</p>
                </div>
              );
            })}
          </div>

          <motion.div 
            initial={{ scale: 0.95 }}
            animate={{ scale: 1 }}
            className={`p-8 rounded-2xl border-2 ${getDecisionColor(reasoning.decision)}`}
          >
            <div className="flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <span className="text-sm font-bold uppercase tracking-wider opacity-80 mb-1 block">Final Decision</span>
                <h2 className="text-4xl font-black capitalize mb-2">{reasoning.decision}</h2>
                <p className="opacity-90">This strategy has been validated against business constraints.</p>
              </div>
              <button
                onClick={handleApply}
                disabled={applying || applied}
                className={`px-8 py-4 rounded-xl font-bold text-lg flex items-center gap-2 transition-all ${
                  applied 
                    ? 'bg-white/50 cursor-not-allowed' 
                    : 'bg-white shadow-sm hover:shadow-md hover:scale-105'
                }`}
              >
                {applied ? (
                  <>Applied <CheckCircle2 className="w-6 h-6" /></>
                ) : applying ? (
                  'Applying...'
                ) : (
                  <>Apply Recommendation <ArrowRight className="w-6 h-6" /></>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default Reasoning;
