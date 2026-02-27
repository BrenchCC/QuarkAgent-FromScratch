import type { TimelineEvent } from "../types/api";

interface EventTimelineProps {
  events: TimelineEvent[];
}

function formatTimestamp(timestamp: string): string {
  const parsedDate = new Date(timestamp);
  if (Number.isNaN(parsedDate.getTime())) {
    return "--:--";
  }

  return parsedDate.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getLabel(type: TimelineEvent["type"]): string {
  if (type === "tool_start") {
    return "TOOL START";
  }

  if (type === "tool_end") {
    return "TOOL END";
  }

  return type.toUpperCase();
}

export default function EventTimeline(props: EventTimelineProps) {
  const { events } = props;

  return (
    <aside className="event-timeline">
      <h3>Live Events</h3>
      {events.length === 0 ? (
        <p className="empty-tip">No events yet.</p>
      ) : (
        <ul>
          {events.map((event) => (
            <li key={event.id}>
              <span className={`event-tag ${event.type}`}>{getLabel(event.type)}</span>
              <span className="event-time">{formatTimestamp(event.timestamp)}</span>
              <pre>{JSON.stringify(event.data, null, 2)}</pre>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
