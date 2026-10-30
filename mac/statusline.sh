#!/bin/bash
# Status line per Claude Code: mostra i limiti di utilizzo in fondo al terminale
# e salva le percentuali in ~/.claude/usage-state.json per il widget nella barra dei menu.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"
in=$(cat)
state="$HOME/.claude/usage-state.json"

# Salva lo stato solo se Claude Code ha passato i dati dei limiti
if jq -e '.rate_limits.five_hour // .rate_limits.seven_day' >/dev/null 2>&1 <<<"$in"; then
  jq -c --argjson t "$(date +%s)" \
    '{updated_at: $t, five_hour: .rate_limits.five_hour, seven_day: .rate_limits.seven_day}' \
    <<<"$in" > "$state.tmp" && mv "$state.tmp" "$state"
fi

# Riga mostrata nel terminale
jq -r '
  def bar($p): ($p/10|floor) as $n | ([range(0;$n)]|map("▓")|join("")) + ([range($n;10)]|map("░")|join(""));
  (.model.display_name // "Claude") as $m
  | (.rate_limits.five_hour.used_percentage // null) as $fh
  | (.rate_limits.seven_day.used_percentage // null) as $sd
  | if $fh == null then $m
    else "\($m) · 5h \(bar($fh)) \($fh|floor)%" + (if $sd != null then " · sett \($sd|floor)%" else "" end)
    end
' <<<"$in"
