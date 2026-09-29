import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders a committed report's Markdown, styled to the obsidian system (tables, code, headings).
export function ReportView({ content }: { content: string }) {
  return (
    <div className="report-md text-sm leading-relaxed text-muted-foreground">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
