import { GroupCard } from "@/components/group-card";
import { Reveal } from "@/components/reveal";
import { SpotlightCard } from "@/components/spotlight-card";
import { getGroups } from "@/lib/api";
import type { Group } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function GroupsPage() {
  let groups: Group[] = [];
  try {
    groups = await getGroups();
  } catch {
    // API unreachable
  }
  const violations = groups.filter((g) => !g.consistent).length;

  return (
    <div className="flex flex-col gap-8 pt-8 pb-16">
      <Reveal>
        <header className="flex flex-col gap-3">
          <span className="eyebrow">correlated groups</span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Markets that must agree
          </h1>
          <p className="max-w-[66ch] text-muted-foreground">
            Some markets are logically linked — winning a title implies winning a race; a higher
            price threshold implies every lower one. Their probabilities <em>must</em> obey an
            ordering. Parallax checks that ordering live; a breach is a provable mispricing, not a
            model opinion.{" "}
            {groups.length > 0 ? (
              <span className="text-foreground">
                {violations > 0
                  ? `${violations} of ${groups.length} groups currently show a violation.`
                  : `All ${groups.length} groups are currently consistent.`}
              </span>
            ) : null}
          </p>
        </header>
      </Reveal>

      {groups.length === 0 ? (
        <div className="panel px-6 py-16 text-center text-sm text-muted-foreground">
          No correlated groups configured.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {groups.map((g, i) => (
            <Reveal key={g.id} delay={0.05 * i}>
              <SpotlightCard className="panel h-full" lift>
                <GroupCard group={g} />
              </SpotlightCard>
            </Reveal>
          ))}
        </div>
      )}
    </div>
  );
}
