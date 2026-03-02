import { Card, CardTitle } from "@/components/ui";
import { RISK_CHART_COLORS } from "@/lib/colors";
import type { RiskCategory } from "@/types";

interface Props {
  score: number;
  category: RiskCategory;
}

export function RiskGauge({ score, category }: Props) {
  const percentage = (score / 1000) * 100;
  const color = RISK_CHART_COLORS[category] ?? "#9ca3af";

  // SVG gauge dimensions
  const cx = 120;
  const cy = 100;
  const r = 80;
  const startAngle = Math.PI;
  const endAngle = 0;
  const angleRange = startAngle - endAngle;
  const needleAngle = startAngle - (percentage / 100) * angleRange;

  const arcPath = (start: number, end: number) => {
    const x1 = cx + r * Math.cos(start);
    const y1 = cy - r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);
    const y2 = cy - r * Math.sin(end);
    const largeArc = start - end > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  const needleX = cx + (r - 10) * Math.cos(needleAngle);
  const needleY = cy - (r - 10) * Math.sin(needleAngle);

  return (
    <Card>
      <CardTitle className="mb-4">Risk Score Gauge</CardTitle>
      <div className="flex flex-col items-center">
        <svg width="240" height="140" viewBox="0 0 240 140">
          {/* Background arc */}
          <path
            d={arcPath(startAngle, endAngle)}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="16"
            strokeLinecap="round"
          />
          {/* Colored arc (filled portion) */}
          <path
            d={arcPath(startAngle, needleAngle)}
            fill="none"
            stroke={color}
            strokeWidth="16"
            strokeLinecap="round"
          />
          {/* Needle */}
          <line
            x1={cx}
            y1={cy}
            x2={needleX}
            y2={needleY}
            stroke="#1f2937"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <circle cx={cx} cy={cy} r="5" fill="#1f2937" />

          {/* Labels */}
          <text x="30" y="115" className="text-[10px]" fill="#9ca3af">
            0
          </text>
          <text x="200" y="115" className="text-[10px]" fill="#9ca3af">
            1000
          </text>
          <text
            x={cx}
            y={cy + 30}
            textAnchor="middle"
            className="text-lg font-bold"
            fill="#111827"
          >
            {score}
          </text>
        </svg>

        <div className="mt-2 flex gap-4 text-xs text-gray-400">
          <span>0–250 Low</span>
          <span>250–500 Medium</span>
          <span>500–750 High</span>
          <span>750+ Very High</span>
        </div>
      </div>
    </Card>
  );
}
