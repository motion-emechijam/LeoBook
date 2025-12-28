"""
Extractor Module
Handles extraction of leagues and matches from Football.com schedule pages.
"""

import asyncio
from typing import List, Dict

from playwright.async_api import Page

from Neo.selector_manager import SelectorManager
from Helpers.constants import WAIT_FOR_LOAD_STATE_TIMEOUT


async def extract_league_matches(page: Page, target_date: str) -> List[Dict]:
    """
    Extract matches using robust hardcoded selectors with intelligent fallbacks.
    """
    print("  [Harvest] Starting match extraction...")
    all_matches = []

    # Priority-based selector system for Football.com matches
    selector_sets = [
        # Primary selectors (Football.com specific)
        {
            "league_header": "section.match-card-section.match-card div.header",
            "match_rows": "section.match-card-section.match-card",
            "match_url": "section.match-card-section.match-card a.card-link"
        },
        # Secondary selectors (generic football site patterns)
        {
            "league_header": ".league-header, [class*='league'] h4, [class*='league'] h3",
            "match_rows": ".match-card, .match-row, [class*='match']",
            "match_url": ".match-card a, .match-row a, [class*='match'] a"
        },
        # Tertiary selectors (very generic)
        {
            "league_header": "h4, h3, .header",
            "match_rows": ".card, .row, [class*='item']",
            "match_url": "a[href*='match'], a[href*='game']"
        }
    ]

    # Try each selector set in priority order
    working_selectors = None
    for i, selector_set in enumerate(selector_sets):
        try:
            # Test if selectors work on the page
            league_count = await page.locator(selector_set["league_header"]).count()
            match_count = await page.locator(selector_set["match_rows"]).count()

            if league_count > 0 and match_count > 0:
                working_selectors = selector_set
                print(f"  [Harvest] Using selector set {i+1}: Found {league_count} leagues, {match_count} matches")
                break
        except Exception as e:
            print(f"  [Harvest] Selector set {i+1} failed: {e}")
            continue

    if not working_selectors:
        print("  [Harvest] No working selectors found")
        return all_matches

    try:
        await asyncio.sleep(2.0)

        # Extract all matches using the working selectors
        matches_data = await page.evaluate("""(selectors, targetDate) => {
            const results = [];

            // Find all league headers
            const leagueHeaders = document.querySelectorAll(selectors.league_header);
            console.log(`Found ${leagueHeaders.length} league headers`);

            // Find all match rows
            const matchRows = document.querySelectorAll(selectors.match_rows);
            console.log(`Found ${matchRows.length} match rows`);

            // Process each league
            leagueHeaders.forEach((header, leagueIndex) => {
                try {
                    // Extract league name
                    const leagueNameEl = header.querySelector('h4, h3') || header;
                    const leagueName = leagueNameEl.textContent ? leagueNameEl.textContent.trim() : `League ${leagueIndex + 1}`;

                    // Find matches that belong to this league
                    const leagueMatches = [];
                    for (const matchRow of matchRows) {
                        // Check if this match comes after the current league header
                        if (header.compareDocumentPosition(matchRow) & Node.DOCUMENT_POSITION_FOLLOWING) {
                            // Check if it comes before the next league header
                            let belongsToLeague = true;
                            for (let i = leagueIndex + 1; i < leagueHeaders.length; i++) {
                                const nextHeader = leagueHeaders[i];
                                if (!(nextHeader.compareDocumentPosition(matchRow) & Node.DOCUMENT_POSITION_FOLLOWING)) {
                                    belongsToLeague = false;
                                    break;
                                }
                            }
                            if (belongsToLeague) {
                                leagueMatches.push(matchRow);
                            }
                        }
                    }

                    console.log(`League "${leagueName}": ${leagueMatches.length} matches`);

                    // Extract data from each match
                    leagueMatches.forEach(matchRow => {
                        try {
                            // Extract team names
                            const homeTeamEl = matchRow.querySelector('.home-team-name, .team-name:first-child, [class*="home"], .home');
                            const awayTeamEl = matchRow.querySelector('.away-team-name, .team-name:last-child, [class*="away"], .away');

                            // Extract time
                            const timeEl = matchRow.querySelector('.match-time, .gmt-time, [class*="time"], .time');

                            // Extract URL
                            const urlEl = matchRow.querySelector(selectors.match_url) ||
                                        matchRow.querySelector('a') ||
                                        matchRow.closest('a');

                            if (homeTeamEl && awayTeamEl) {
                                const homeTeam = homeTeamEl.textContent ? homeTeamEl.textContent.trim() : 'Unknown';
                                const awayTeam = awayTeamEl.textContent ? awayTeamEl.textContent.trim() : 'Unknown';
                                const time = timeEl ? (timeEl.textContent ? timeEl.textContent.trim() : 'N/A') : 'N/A';
                                const url = urlEl ? (urlEl.href || urlEl.getAttribute('href') || '') : '';

                                results.push({
                                    home: homeTeam,
                                    away: awayTeam,
                                    time: time,
                                    league: leagueName,
                                    url: url,
                                    date: targetDate
                                });
                            }
                        } catch (matchError) {
                            console.log('Error processing match:', matchError);
                        }
                    });

                } catch (leagueError) {
                    console.log('Error processing league:', leagueError);
                }
            });

            return results;
        }""", working_selectors, target_date)

        if matches_data and len(matches_data) > 0:
            all_matches.extend(matches_data)
            print(f"  [Harvest] Successfully extracted {len(matches_data)} matches")
        else:
            print("  [Harvest] No matches found with current selectors")

    except Exception as e:
        print(f"  [Harvest] Extraction failed: {e}")

    print(f"  [Harvest] Total matches found: {len(all_matches)}")
    return all_matches
 

async def validate_match_data(matches: List[Dict]) -> List[Dict]:
    """Validate and clean extracted match data."""
    valid_matches = []
    for match in matches:
        if all(k in match for k in ['home', 'away', 'url', 'league']):
            # Basic validation
            if match['home'] and match['away'] and match['url']:
                valid_matches.append(match)
        else:
            print(f"    [Validation] Skipping invalid match: {match}")
    print(f"  [Validation] {len(valid_matches)}/{len(matches)} matches valid.")
    return valid_matches
