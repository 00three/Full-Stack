'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

const DataGlobe = ({ isIlluminated, isExploding }: { isIlluminated: boolean, isExploding: boolean }) => {
  // Generate random stars for the background
  const [stars, setStars] = useState<{x: number, y: number, size: number, opacity: number}[]>([]);
  useEffect(() => {
    const timerId = setTimeout(() => {
      const generated = Array.from({ length: 150 }).map(() => ({
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 2 + 0.5,
        opacity: Math.random() * 0.8 + 0.2
      }));
      setStars(generated);
    }, 0);
    return () => clearTimeout(timerId);
  }, []);

  return (
    <div className={`absolute inset-0 flex items-center justify-center overflow-hidden transition-all duration-2000 pointer-events-none ${isIlluminated ? 'opacity-80 scale-100' : 'opacity-10 scale-95'}`}>
      {/* Starfield */}
      <div className="absolute inset-0 transition-opacity duration-1000" style={{ opacity: isIlluminated ? 0.7 : 0.2 }}>
        {stars.map((star, i) => (
          <motion.div
            key={i}
            animate={isExploding ? { 
              scale: [1, 20], 
              opacity: [star.opacity, 0], 
              x: (star.x - 50) * 15, 
              y: (star.y - 50) * 15 
            } : { opacity: star.opacity }}
            transition={isExploding ? { duration: 1.2, ease: "circIn" } : { duration: 0 }}
            className="absolute bg-white rounded-full"
            style={{
              left: `${star.x}%`,
              top: `${star.y}%`,
              width: `${star.size}px`,
              height: `${star.size}px`,
              boxShadow: `0 0 ${star.size * 2}px rgba(255,255,255,0.8)`
            }}
          />
        ))}
      </div>

      <motion.div 
        animate={isExploding ? { scale: 5, opacity: 0 } : { scale: 1, opacity: 1 }}
        transition={isExploding ? { duration: 1, ease: 'easeInOut' } : { duration: 1 }}
        className="relative w-[150vw] h-[150vw] sm:w-[90vw] sm:h-[90vw] max-w-[1200px] max-h-[1200px] flex items-center justify-center"
      >
        {/* Abstract Globe Rings */}
        <motion.div 
          animate={isExploding ? {} : { rotate: 360 }} 
          transition={{ duration: 120, repeat: Infinity, ease: "linear" }} 
          className="absolute w-full h-full border border-white/10 rounded-full shadow-[0_0_50px_rgba(255,255,255,0.05)_inset]"
        >
          {/* Outer Ring Nodes */}
          <div className="absolute top-[10%] left-[20%] w-1 h-1 bg-accent rounded-full shadow-[0_0_8px_rgba(142,142,142,0.8)]" />
          <div className="absolute bottom-[20%] right-[10%] w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_12px_rgba(255,255,255,0.8)]" />
        </motion.div>
        <motion.div 
          animate={isExploding ? {} : { rotate: -360 }} 
          transition={{ duration: 150, repeat: Infinity, ease: "linear" }} 
          className="absolute w-[85%] h-[85%] border border-dashed border-white/20 rounded-full"
        >
          {/* Orbiting Nodes */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full shadow-[0_0_15px_rgba(255,255,255,1)]" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-1.5 h-1.5 bg-accent rounded-full shadow-[0_0_10px_rgba(142,142,142,0.8)]" />
          <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 w-1 h-1 bg-white rounded-full shadow-[0_0_5px_rgba(255,255,255,0.8)]" />
        </motion.div>
        <motion.div 
          animate={isExploding ? {} : { rotate: 360 }} 
          transition={{ duration: 90, repeat: Infinity, ease: "linear" }} 
          className="absolute w-[60%] h-[60%] border border-white/10 rounded-full"
        >
          <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 bg-white rounded-full shadow-[0_0_20px_rgba(255,255,255,1)]" />
          <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-2 h-2 bg-accent rounded-full shadow-[0_0_10px_rgba(142,142,142,0.8)]" />
        </motion.div>
        <motion.div 
          animate={isExploding ? {} : { rotate: -360 }} 
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }} 
          className="absolute w-[35%] h-[35%] border border-dashed border-white/30 rounded-full shadow-[0_0_30px_rgba(255,255,255,0.1)]"
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,0.9)]" />
        </motion.div>
        
        {/* Converging 'News' Data Streams */}
        <div className="absolute inset-0 pointer-events-none">
          {[...Array(8)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute top-1/2 left-1/2 w-[2px] h-48 bg-gradient-to-t from-transparent via-white/60 to-transparent filter blur-[1px]"
              style={{ originY: 0 }}
              initial={{ rotate: i * 45, scaleY: 0, opacity: 0 }}
              animate={isExploding ? { scaleY: 0, opacity: 0 } : { 
                scaleY: [0, 1.5, 0],
                opacity: [0, 0.8, 0],
                y: [300, 0] 
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                delay: i * 0.4,
                ease: "easeInOut"
              }}
            />
          ))}
        </div>
      </motion.div>
    </div>
  );
};

export default function PradaSpotlightHero({ onQuickStart }: { onQuickStart?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isIlluminated, setIsIlluminated] = useState(false);
  const [isExploding, setIsExploding] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  
  // To create trails
  const [trail, setTrail] = useState<{x: number, y: number, id: number}[]>([]);
  const trailIdCounter = useRef(0);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      setMousePos({ x, y });

      if (isDragging && isIlluminated) {
        setTrail(prev => [
          ...prev.slice(-10), 
          { x, y, id: trailIdCounter.current++ }
        ]);
      }
    };

    const handleMouseDown = () => {
      if (!isIlluminated) {
        setIsIlluminated(true);
      } else {
        setIsDragging(true);
      }
    };

    const handleMouseUp = () => setIsDragging(false);

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isIlluminated, isDragging]);

  // Clean up trails
  useEffect(() => {
    if (trail.length > 0) {
      const timer = setTimeout(() => {
        setTrail(prev => prev.slice(1));
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [trail]);

  // Spotlight radius expanding on click
  const spotlightRadius = isIlluminated ? '150vh' : '20vw';

  return (
    <div 
      ref={containerRef}
      className={`relative w-full h-screen bg-bg overflow-hidden cursor-crosshair flex items-center justify-center flex-col p-10 transition-colors duration-1000 ${isIlluminated ? (isExploding ? 'bg-white' : 'bg-[#0a0a0a]') : 'bg-[#000000]'}`}
    >
      <DataGlobe isIlluminated={isIlluminated} isExploding={isExploding} />

      {/* Top Navigation */}
      <header className="absolute top-0 left-0 w-full p-6 sm:p-10 flex flex-col sm:flex-row justify-between items-center sm:items-start z-50 pointer-events-auto gap-4">
        <div className={`text-[9px] sm:text-[10px] tracking-[0.4em] uppercase text-accent transition-opacity duration-1000 ${isIlluminated ? 'opacity-100' : 'opacity-40 hover:opacity-100'}`}>
          Prism AI / Intelligence Unit
        </div>
        <nav className={`flex gap-6 sm:gap-10 text-[10px] sm:text-[11px] uppercase tracking-[0.2em] font-light text-ink transition-opacity duration-1000 ${isIlluminated ? 'opacity-100' : 'opacity-20 hover:opacity-100'}`}>
          <a href="#" className="hover:text-accent transition-colors">Archives</a>
          <a href="#" className="hover:text-accent transition-colors">Synthesis</a>
          <a href="#" className="hover:text-accent transition-colors">Editorial</a>
        </nav>
      </header>

      {/* Side Rails */}
      <div className={`absolute left-4 sm:left-10 top-1/2 -translate-y-1/2 -rotate-180 [writing-mode:vertical-rl] text-[8px] sm:text-[9px] uppercase tracking-[0.3em] text-accent transition-opacity duration-1000 hidden sm:block ${isIlluminated ? 'opacity-60' : 'opacity-20'}`}>
        RAG Protocol 8.24 — Synchronized Live
      </div>
      <div className={`absolute right-4 sm:right-10 top-1/2 -translate-y-1/2 [writing-mode:vertical-rl] text-[8px] sm:text-[9px] uppercase tracking-[0.3em] text-accent transition-opacity duration-1000 hidden sm:block ${isIlluminated ? 'opacity-60' : 'opacity-20'}`}>
        Real-Time Distribution — Global Nodes
      </div>

      <p className={`absolute text-accent text-[9px] sm:text-[10px] tracking-[0.4em] font-sans top-24 sm:top-32 text-center w-full uppercase z-10 transition-opacity duration-1000 ${isIlluminated ? 'opacity-0 pointer-events-none' : 'opacity-60'}`}>
        Click to illuminate sequence
      </p>

      {/* The main Logo hidden in the dark */}
      <div className={`absolute inset-0 flex flex-col items-center justify-center pointer-events-none transition-opacity duration-1000 ${isIlluminated ? 'opacity-30' : 'opacity-10'}`}>
        <h1 className="text-[15vw] sm:text-[12vw] font-serif tracking-[0.3em] text-[#111] leading-none select-none uppercase pl-[0.3em]">
          OOTHREE
        </h1>
        <div className="absolute mt-32 sm:mt-48 text-[8px] sm:text-[10px] tracking-[0.4em] font-sans text-accent uppercase">
          Autogenerative News Studio
        </div>
      </div>

      {/* The illuminated layer with dynamic mask */}
      <motion.div
        className="absolute inset-0 z-20 pointer-events-none flex items-center justify-center mix-blend-screen"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div 
          className="w-full h-full absolute flex flex-col items-center justify-center transition-all duration-300 ease-out"
          style={{
            background: `radial-gradient(circle at ${mousePos.x}px ${mousePos.y}px, rgba(255,255,255,0.08) 0%, transparent ${spotlightRadius})`,
            WebkitMaskImage: `radial-gradient(circle at ${mousePos.x}px ${mousePos.y}px, black 0%, transparent ${spotlightRadius})`,
            maskImage: `radial-gradient(circle at ${mousePos.x}px ${mousePos.y}px, black 0%, transparent ${spotlightRadius})`
          }}
        >
          <h1 
            className="text-[15vw] sm:text-[12vw] font-serif tracking-[0.3em] leading-none select-none uppercase pl-[0.3em]"
            style={{ 
              background: 'linear-gradient(90deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,1) 50%, rgba(255,255,255,0.3) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              textShadow: isIlluminated ? '0 0 40px rgba(255,255,255,0.2)' : '0 0 20px rgba(255,255,255,0.4)'
            }}
          >
            OOTHREE
          </h1>
          <div className="absolute mt-32 sm:mt-48 text-[8px] sm:text-[10px] tracking-[0.4em] font-sans text-ink uppercase">
            Autogenerative News Studio
          </div>
        </div>

        {/* Light Trails / Glass Reflection layer */}
        <AnimatePresence>
          {trail.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0.4, scale: 0.5 }}
              animate={{ opacity: 0, scale: 2 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.5, ease: "easeOut" }}
              className="absolute rounded-full pointer-events-none mix-blend-screen"
              style={{
                left: t.x - 50,
                top: t.y - 50,
                width: 100,
                height: 100,
                background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
                boxShadow: '0 0 20px rgba(255,255,255,0.05)'
              }}
            />
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Subtle dust particles overlay */}
      <div 
        className={`absolute inset-0 pointer-events-none transition-opacity duration-1000 mix-blend-screen ${isIlluminated ? 'opacity-20' : 'opacity-5'}`}
        style={{
          background: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Quick Start Button */}
      <motion.button
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: isIlluminated && !isExploding ? 1 : 0, y: isIlluminated ? 0 : 20, pointerEvents: isIlluminated && !isExploding ? 'auto' : 'none' }}
        transition={{ duration: 1, delay: 0.5 }}
        onClick={(e) => {
          e.stopPropagation();
          setIsExploding(true);
          setTimeout(() => {
            onQuickStart?.();
          }, 1200);
        }}
        className="absolute bottom-12 sm:bottom-16 text-[10px] uppercase tracking-[0.3em] font-sans text-ink border border-white/20 px-8 py-3 hover:bg-white hover:text-black transition-all duration-500 z-50 rounded-none bg-black/50 backdrop-blur-sm"
      >
        Quick Start
      </motion.button>
    </div>
  );
}

