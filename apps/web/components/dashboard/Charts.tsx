"use client";

import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  Radar, RadarChart, PolarAngleAxis, PolarGrid,
} from "recharts";

const trend = [
  { week: "W1", score: 6.8, confidence: 70 },
  { week: "W2", score: 7.1, confidence: 74 },
  { week: "W3", score: 7.4, confidence: 78 },
  { week: "W4", score: 7.8, confidence: 83 },
  { week: "W5", score: 8.0, confidence: 86 },
];

const skills = [
  { skill: "Technical", v: 78 },
  { skill: "Comms", v: 84 },
  { skill: "Confidence", v: 88 },
  { skill: "Alignment", v: 82 },
  { skill: "Culture", v: 76 },
];

const tooltipStyle = {
  background: "#0b1830", border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12, color: "#E8ECF4", fontSize: 12,
};

export function TrendChart() {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={trend}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6C63FF" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#6C63FF" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="week" stroke="#8A95A8" fontSize={12} />
        <YAxis stroke="#8A95A8" fontSize={12} domain={[6, 9]} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="score" stroke="#6C63FF" strokeWidth={2} fill="url(#g)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SkillRadar() {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={skills}>
        <PolarGrid stroke="rgba(255,255,255,0.1)" />
        <PolarAngleAxis dataKey="skill" tick={{ fill: "#8A95A8", fontSize: 12 }} />
        <Radar dataKey="v" stroke="#4CC9F0" fill="#4CC9F0" fillOpacity={0.35} />
        <Tooltip contentStyle={tooltipStyle} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
