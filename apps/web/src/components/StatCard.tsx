import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "blue" | "mint" | "amber" | "rose";
}

export function StatCard({ label, value, detail, icon: Icon, tone = "blue" }: StatCardProps) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-icon">
        <Icon size={19} />
      </div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

