import { useEffect, useState } from "react";
import { ExternalLink, Lightbulb, Play, RefreshCw, TrendingUp, Video } from "lucide-react";
import { fetchYouTubeDigest } from "../api";
import { formatDateTime } from "../format";
import type { DailyYouTubeDigest } from "../types";

export function YouTubeBriefing() {
  const [digest, setDigest] = useState<DailyYouTubeDigest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    void fetchYouTubeDigest()
      .then((next) => {
        setDigest(next);
        setError(null);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "YouTube digest failed"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    void fetchYouTubeDigest()
      .then((next) => {
        if (!active) return;
        setDigest(next);
        setError(null);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "YouTube digest failed");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <section className="youtube-briefing">
      <div className="youtube-summary-card">
        <div className="youtube-title-row">
          <div className="youtube-icon"><Video size={24} /></div>
          <div>
            <span className="section-kicker">Daily video desk · India</span>
            <h2>{digest?.headline ?? "Loading the daily channel brief…"}</h2>
          </div>
          <button className="icon-button" type="button" onClick={load} aria-label="Refresh YouTube digest">
            <RefreshCw className={loading ? "spin" : ""} size={17} />
          </button>
        </div>
        {error && <p className="youtube-error">{error}</p>}
        {digest && (
          <>
            <p className="youtube-lead">{digest.summary}</p>
            <div className="youtube-digest-stats">
              <div><strong>{digest.total_videos}</strong><span>Videos</span></div>
              <div><strong>{digest.covered_channels}/{digest.configured_channels}</strong><span>Channels active</span></div>
              <div><strong>{digest.date}</strong><span>IST edition</span></div>
            </div>
            <small className="method-note">{digest.methodology}</small>
          </>
        )}
      </div>

      {digest && digest.recommended_videos.length > 0 && (
        <section className="video-recommendations">
          <header>
            <div><span className="section-kicker">Watch with purpose</span><h2>Recommended daily viewing</h2></div>
            <Lightbulb size={21} />
          </header>
          <div className="recommended-video-grid">
            {digest.recommended_videos.map((item) => (
              <a href={item.video.url} target="_blank" rel="noreferrer" key={item.video.video_id}>
                <div className="recommended-video-meta"><span>{item.video.channel_name}</span><strong>{Math.round(item.relevance_score)} relevance</strong></div>
                <h3>{item.video.title}</h3>
                <p>{item.why_recommended}</p>
                <ul>{item.flashpoints.map((point) => <li key={point}>{point}</li>)}</ul>
                <small><Play size={12} /> Open source video</small>
              </a>
            ))}
          </div>
          <p className="transcript-boundary">Flashpoints are derived from public title, description and linked-symbol metadata. They are not claims that a protected third-party transcript was analyzed.</p>
        </section>
      )}

      {digest && digest.stock_research_ideas.length > 0 && (
        <section className="video-stock-ideas">
          <header><TrendingUp size={19} /><div><span className="section-kicker">Ideas to investigate</span><h2>Stocks appearing in today’s video evidence</h2></div></header>
          <div>{digest.stock_research_ideas.map((idea) => <article key={idea.symbol}><span>{idea.mention_count} mentions</span><h3>{idea.symbol.replace(".NS", "")}</h3><p>{idea.context}</p><small>{idea.evidence_titles.join(" · ")}</small></article>)}</div>
        </section>
      )}

      <div className="youtube-channel-grid">
        {digest?.channels.map((channel) => (
          <article className="youtube-channel" key={channel.channel_handle}>
            <header>
              <div><span>Priority {channel.priority} · {channel.language?.toUpperCase()}</span><h3>{channel.channel_name}</h3></div>
              <strong>{channel.video_count}</strong>
            </header>
            <p className="channel-summary">{channel.summary}</p>
            <div className="video-list">
              {channel.videos.map((video) => (
                <a href={video.url} target="_blank" rel="noreferrer" className="video-row" key={video.video_id}>
                  <Play size={15} />
                  <div>
                    <strong>{video.title}</strong>
                    {video.summary && <p>{video.summary}</p>}
                    <span>
                      {formatDateTime(video.published_at)}
                      {video.view_count !== null ? ` · ${video.view_count.toLocaleString()} views` : ""}
                      {video.symbols.length ? ` · ${video.symbols.join(", ")}` : ""}
                    </span>
                  </div>
                  <ExternalLink size={13} />
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
