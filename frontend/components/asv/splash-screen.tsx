"use client"

import { motion } from "framer-motion"
import { useEffect, useState } from "react"

export function SplashScreen({ onComplete }: { onComplete: () => void }) {
  const [showText, setShowText] = useState(false)

  useEffect(() => {
    const textTimer = setTimeout(() => setShowText(true), 500)
    const completeTimer = setTimeout(onComplete, 3000)
    return () => {
      clearTimeout(textTimer)
      clearTimeout(completeTimer)
    }
  }, [onComplete])

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-6">
      {/* Enhanced Animated Background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Soft gradient orbs */}
        <motion.div
          className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-primary/10 blur-3xl"
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.4, 0.6, 0.4],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -bottom-32 -right-32 h-80 w-80 rounded-full bg-primary/8 blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute left-1/4 top-1/4 h-64 w-64 rounded-full bg-primary/5 blur-3xl"
          animate={{
            x: [0, 50, 0],
            y: [0, 30, 0],
            opacity: [0.2, 0.4, 0.2],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        />
        
        {/* Subtle waveform background lines */}
        <svg className="absolute bottom-20 left-0 right-0 h-48 opacity-[0.06]" viewBox="0 0 400 100" preserveAspectRatio="none">
          <motion.path
            d="M0 50 Q25 20 50 50 T100 50 T150 50 T200 50 T250 50 T300 50 T350 50 T400 50"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            className="text-primary"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 3, delay: 0.5 }}
          />
          <motion.path
            d="M0 60 Q25 35 50 60 T100 60 T150 60 T200 60 T250 60 T300 60 T350 60 T400 60"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            className="text-primary"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 3, delay: 0.8 }}
          />
          <motion.path
            d="M0 70 Q25 50 50 70 T100 70 T150 70 T200 70 T250 70 T300 70 T350 70 T400 70"
            stroke="currentColor"
            strokeWidth="0.5"
            fill="none"
            className="text-primary"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 3, delay: 1.1 }}
          />
        </svg>
        
        {/* Floating particles */}
        {[...Array(8)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-1 w-1 rounded-full bg-primary/30"
            style={{
              left: `${10 + i * 12}%`,
              top: `${15 + (i % 4) * 20}%`,
            }}
            animate={{
              y: [0, -30, 0],
              opacity: [0.2, 0.6, 0.2],
              scale: [1, 1.5, 1],
            }}
            transition={{
              duration: 4 + i * 0.5,
              repeat: Infinity,
              delay: i * 0.3,
              ease: "easeInOut",
            }}
          />
        ))}
        
        {/* Subtle grid pattern */}
        <div 
          className="absolute inset-0 opacity-[0.015]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
            backgroundSize: '32px 32px'
          }}
        />
      </div>

      {/* Main Content */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="relative z-10 flex flex-col items-center"
      >
        {/* Logo */}
        <div className="relative mb-8">
          <motion.div
            className="flex h-24 w-24 items-center justify-center rounded-3xl bg-primary shadow-2xl shadow-primary/30"
            initial={{ rotate: -10 }}
            animate={{ rotate: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <span className="text-4xl font-bold tracking-tight text-primary-foreground">
              ASV
            </span>
          </motion.div>
          
          {/* Multiple pulse rings */}
          <motion.div
            className="absolute -inset-2 rounded-3xl border-2 border-primary/30"
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{ scale: 1.3, opacity: 0 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
          />
          <motion.div
            className="absolute -inset-2 rounded-3xl border border-primary/20"
            initial={{ scale: 1, opacity: 0.3 }}
            animate={{ scale: 1.5, opacity: 0 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.3 }}
          />
        </div>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: showText ? 1 : 0, y: showText ? 0 : 10 }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-lg font-light tracking-widest text-muted-foreground"
        >
          A Silent Voice
        </motion.p>

        {/* Animated waveform */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: showText ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-1"
        >
          {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <motion.div
              key={i}
              className="w-1 rounded-full bg-primary/60"
              animate={{
                height: [6, 24, 6],
              }}
              transition={{
                duration: 1,
                repeat: Infinity,
                delay: i * 0.08,
                ease: "easeInOut",
              }}
            />
          ))}
        </motion.div>
      </motion.div>

      {/* Bottom tagline */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: showText ? 0.6 : 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="absolute bottom-12 text-sm text-muted-foreground"
      >
        Empowering silent communication
      </motion.p>
    </div>
  )
}
