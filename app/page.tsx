'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import PradaSpotlightHero from './components/PradaSpotlightHero';
import NewsDashboard from './components/NewsDashboard';

export default function Home() {
  const [showDashboard, setShowDashboard] = useState(false);

  return (
    <main className="bg-black min-h-screen">
      <AnimatePresence mode="wait">
        {!showDashboard ? (
          <motion.div
            key="hero"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
            className="w-full h-screen"
          >
            <PradaSpotlightHero onQuickStart={() => setShowDashboard(true)} />
          </motion.div>
        ) : (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <NewsDashboard />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
