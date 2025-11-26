"""
Django management command to review headlines for potential missing tokens.

This command:
1. Fetches all headlines from the past 24 hours
2. Uses regex to detect potential token mentions
3. Compares against the Leviathan API token list
4. Reports potential missing tokens that might need to be added
"""

import re
import json
from django.core.management.base import BaseCommand
from squid_digest.tools.leviathan import LeviathanNewsFetcher


class Command(BaseCommand):
    help = 'Review all headlines from past 24 hours for potential missing tokens'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each headline',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Show raw JSON data for debugging token detection',
        )
        parser.add_argument(
            '--debug-token',
            type=str,
            help='Debug a specific token (e.g., WLFI, BTC)',
        )
        parser.add_argument(
            '--show-readiness',
            action='store_true',
            help='Always show detailed readiness information for all articles',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        debug = options['debug']
        debug_token = (options.get('debug_token') or '').upper()
        show_readiness = options.get('show_readiness', False)
        
        self.stdout.write(self.style.SUCCESS('🔍 Reviewing headlines for potential missing tokens...\n'))
        
        # Fetch all news from past 24 hours
        self.stdout.write('📰 Fetching all news from past 24 hours...')
        fetcher = LeviathanNewsFetcher()
        
        try:
            all_news = fetcher.fetch_all_news_24h(save=False)
            self.stdout.write(self.style.SUCCESS(f'✓ Found {len(all_news)} news items\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to fetch news: {e}'))
            return
        
        # Fetch token list
        self.stdout.write('🪙 Fetching token list from Leviathan API...')
        try:
            token_data = fetcher.fetch_tokens(save=False)
            tokens = token_data.get('tokens', [])
            self.stdout.write(self.style.SUCCESS(f'✓ Found {len(tokens)} tracked tokens\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to fetch tokens: {e}'))
            return
        
        # Build token symbol and name sets for quick lookup
        # Note: Token symbols may include $ prefix, so we store both with and without $
        token_symbols = set()
        token_names = {token.get('name', '').upper() for token in tokens if token.get('name')}
        
        for token in tokens:
            symbol = token.get('symbol', '')
            if symbol:
                symbol_upper = symbol.upper()
                token_symbols.add(symbol_upper)  # Add as-is (e.g., "$WLFI")
                # Also add without $ prefix for matching (e.g., "WLFI")
                if symbol_upper.startswith('$'):
                    token_symbols.add(symbol_upper[1:])  # Strip $ prefix
        
        # Also extract tokens from news items' tags (they may have token info embedded)
        tokens_from_tags = set()
        for news_item in all_news:
            tags = news_item.get('tags', [])
            for tag in tags:
                if tag.get('is_token_tag') and tag.get('token'):
                    token_data = tag['token']
                    symbol = token_data.get('symbol', '')
                    if symbol:
                        symbol_upper = symbol.upper()
                        tokens_from_tags.add(symbol_upper)
                        if symbol_upper.startswith('$'):
                            tokens_from_tags.add(symbol_upper[1:])
                    name = token_data.get('name', '')
                    if name:
                        token_names.add(name.upper())
        
        # Merge tokens from tags into main token sets
        token_symbols.update(tokens_from_tags)
        
        # Debug: Show token list if debugging
        if debug or debug_token:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('🔍 DEBUG: Token List from API'))
            self.stdout.write('='*80)
            
            if debug_token:
                # Show only tokens matching the debug token
                matching_tokens = [
                    t for t in tokens 
                    if t.get('symbol', '').upper() == debug_token or 
                       t.get('name', '').upper() == debug_token
                ]
                if matching_tokens:
                    self.stdout.write(f'\nFound {len(matching_tokens)} token(s) matching "{debug_token}":\n')
                    for token in matching_tokens:
                        self.stdout.write(json.dumps(token, indent=2))
                        self.stdout.write('\n')
                else:
                    self.stdout.write(f'\n⚠️  No tokens found matching "{debug_token}"\n')
                    self.stdout.write(f'Available symbols: {sorted(list(token_symbols))[:50]}...\n')
                    self.stdout.write(f'Available names: {sorted(list(token_names))[:50]}...\n')
            else:
                # Show all tokens
                self.stdout.write(f'\nTotal tokens: {len(tokens)}')
                self.stdout.write(f'Unique symbols: {len(token_symbols)}')
                self.stdout.write(f'Unique names: {len(token_names)}\n')
                self.stdout.write('\nSample tokens (first 10):\n')
                for token in tokens[:10]:
                    self.stdout.write(json.dumps(token, indent=2))
                    self.stdout.write('\n')
            
            self.stdout.write('='*80 + '\n')
        
        # Regex patterns to detect potential token mentions
        # Priority 1: $TOKEN format (most reliable indicator)
        dollar_token_pattern = re.compile(r'\$([A-Z]{2,10})\b')
        
        # Priority 2: Uppercase words that look like token symbols (3-10 chars, alphanumeric)
        # Exclude very short words (2 chars) as they're usually common words
        uppercase_token_pattern = re.compile(r'\b([A-Z]{3,10})\b')
        
        # Priority 3: Token mentions with context
        context_token_pattern = re.compile(
            r'\b([A-Z]{3,10})\s+(?:token|Token|coin|Coin|stablecoin|Stablecoin)\b'
        )
        
        # Common words to exclude (not tokens) - most common English words
        excluded_words = {
            'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE',
            'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW',
            'OLD', 'SEE', 'TWO', 'WHO', 'WAY', 'USE', 'MAN', 'YEAR', 'SAID', 'EACH', 'WHICH',
            'THEIR', 'TIME', 'WILL', 'ABOUT', 'IF', 'INTO', 'MORE', 'VERY', 'WHAT', 'KNOW',
            'JUST', 'FIRST', 'ALSO', 'AFTER', 'BACK', 'OTHER', 'MANY', 'WELL', 'ONLY', 'WORK',
            'LIFE', 'OVER', 'MOST', 'STILL', 'MAKE', 'BEEN', 'BEFORE', 'GREAT', 'WHERE', 'MUCH',
            'SHOULD', 'THROUGH', 'THINK', 'THREE', 'WHILE', 'WORLD', 'MIGHT', 'NEVER', 'UNDER',
            'REALLY', 'SINCE', 'AGAIN', 'AROUND', 'BOTH', 'COME', 'DURING', 'FOUND', 'GOING',
            'HAPPEN', 'HAVING', 'LARGE', 'LATER', 'LEAVE', 'LITTLE', 'LOCAL', 'LONG', 'LOOK',
            'MADE', 'NIGHT', 'OFFER', 'OFTEN', 'ORDER', 'OWNER', 'PARTY', 'PEACE', 'PLACE',
            'PLANT', 'POINT', 'POWER', 'PRICE', 'QUITE', 'RAISE', 'RANGE', 'REACH', 'READY',
            'REAL', 'REASON', 'RECORD', 'REDUCE', 'REFER', 'RELEASE', 'REMAIN', 'REMEMBER',
            'REPLY', 'REPORT', 'RESULT', 'RETURN', 'REVEAL', 'REVENUE', 'REVIEW', 'RISE',
            'RISK', 'ROAD', 'ROCK', 'ROLE', 'ROOM', 'ROOT', 'ROUND', 'ROUTE', 'RULE', 'RUN',
            'SAFE', 'SAID', 'SALE', 'SAME', 'SAVE', 'SAY', 'SCALE', 'SCENE', 'SCHOOL', 'SEA',
            'SEARCH', 'SEASON', 'SEAT', 'SECOND', 'SECRET', 'SECTION', 'SECURITY', 'SEE', 'SEED',
            'SEEK', 'SEEM', 'SELECT', 'SELL', 'SEND', 'SENIOR', 'SENSE', 'SERIES', 'SERIOUS',
            'SERVE', 'SERVICE', 'SESSION', 'SET', 'SETTLE', 'SEVEN', 'SHALL', 'SHAPE', 'SHARE',
            'SHE', 'SHIFT', 'SHINE', 'SHIP', 'SHOCK', 'SHOE', 'SHOOT', 'SHOP', 'SHORE', 'SHORT',
            'SHOT', 'SHOULD', 'SHOULDER', 'SHOW', 'SHUT', 'SICK', 'SIDE', 'SIGHT', 'SIGN',
            'SILENT', 'SILK', 'SILVER', 'SIMILAR', 'SIMPLE', 'SINCE', 'SING', 'SINGLE', 'SINK',
            'SIR', 'SISTER', 'SIT', 'SITE', 'SITUATION', 'SIX', 'SIZE', 'SKILL', 'SKIN', 'SKIP',
            'SKY', 'SLEEP', 'SLIDE', 'SLIGHT', 'SLIP', 'SLOW', 'SMALL', 'SMART', 'SMILE', 'SMOKE',
            'SMOOTH', 'SNAKE', 'SNOW', 'SO', 'SOAP', 'SOCIAL', 'SOFT', 'SOIL', 'SOLAR', 'SOLD',
            'SOLID', 'SOLVE', 'SOME', 'SON', 'SONG', 'SOON', 'SORRY', 'SORT', 'SOUL', 'SOUND',
            'SOUP', 'SOURCE', 'SOUTH', 'SPACE', 'SPARE', 'SPARK', 'SPEAK', 'SPECIAL', 'SPEED',
            'SPELL', 'SPEND', 'SPIRIT', 'SPLIT', 'SPOIL', 'SPONSOR', 'SPORT', 'SPOT', 'SPRAY',
            'SPREAD', 'SPRING', 'SQUARE', 'STABLE', 'STAFF', 'STAGE', 'STAIR', 'STALL', 'STAMP',
            'STAND', 'START', 'STATE', 'STAY', 'STEADY', 'STEAL', 'STEAM', 'STEEL', 'STEP',
            'STICK', 'STILL', 'STING', 'STIR', 'STOCK', 'STONE', 'STOP', 'STORE', 'STORM',
            'STORY', 'STRAIGHT', 'STRANGE', 'STREAM', 'STREET', 'STRESS', 'STRETCH', 'STRICT',
            'STRIKE', 'STRING', 'STRIP', 'STRONG', 'STRUGGLE', 'STUDENT', 'STUFF', 'STYLE',
            'SUBJECT', 'SUBMIT', 'SUCCESS', 'SUCH', 'SUDDEN', 'SUFFER', 'SUGAR', 'SUGGEST',
            'SUIT', 'SUMMER', 'SUN', 'SUPER', 'SUPPLY', 'SUPPORT', 'SUPPOSE', 'SURE', 'SURFACE',
            'SURGE', 'SURPRISE', 'SURROUND', 'SURVEY', 'SURVIVE', 'SUSPECT', 'SWEET', 'SWIFT',
            'SWIM', 'SWING', 'SWITCH', 'SYMBOL', 'SYSTEM', 'TABLE', 'TACKLE', 'TAIL', 'TAKE',
            'TALE', 'TALK', 'TALL', 'TANK', 'TAP', 'TAPE', 'TARGET', 'TASK', 'TASTE', 'TAX',
            'TEA', 'TEACH', 'TEAM', 'TEAR', 'TECH', 'TELL', 'TEN', 'TENT', 'TERM', 'TEST',
            'TEXT', 'THAN', 'THANK', 'THAT', 'THE', 'THEATER', 'THEIR', 'THEM', 'THEME', 'THEN',
            'THEORY', 'THERE', 'THESE', 'THEY', 'THICK', 'THIN', 'THING', 'THINK', 'THIRD',
            'THIS', 'THOSE', 'THOUGH', 'THOUGHT', 'THOUSAND', 'THREAD', 'THREAT', 'THREE',
            'THROW', 'THUS', 'TICKET', 'TIDE', 'TIE', 'TIGHT', 'TILE', 'TIME', 'TINY', 'TIP',
            'TIRED', 'TITLE', 'TO', 'TOAST', 'TODAY', 'TOE', 'TOGETHER', 'TOKEN', 'TOMORROW',
            'TONE', 'TONIGHT', 'TOOL', 'TOOTH', 'TOP', 'TOPIC', 'TOTAL', 'TOWARD', 'TOWER',
            'TOWN', 'TOY', 'TRACK', 'TRADE', 'TRAFFIC', 'TRAIN', 'TRANSFER', 'TRAP', 'TRASH',
            'TRAVEL', 'TRAY', 'TREAT', 'TREE', 'TREND', 'TRIAL', 'TRIBE', 'TRICK', 'TRIGGER',
            'TRIM', 'TRIP', 'TROOP', 'TROPHY', 'TROUBLE', 'TRUCK', 'TRUE', 'TRUST', 'TRUTH',
            'TRY', 'TUBE', 'TUESDAY', 'TUG', 'TUNE', 'TUNNEL', 'TURKEY', 'TURN', 'TV', 'TWELVE',
            'TWENTY', 'TWICE', 'TWIN', 'TWIST', 'TWO', 'TYPE', 'TYPICAL', 'UGLY', 'UNABLE',
            'UNCLE', 'UNDER', 'UNDO', 'UNFAIR', 'UNHAPPY', 'UNIFORM', 'UNIQUE', 'UNIT', 'UNKNOWN',
            'UNTIL', 'UNUSUAL', 'UPDATE', 'UPGRADE', 'UPON', 'UPPER', 'UPSET', 'URBAN', 'URGE',
            'USAGE', 'USE', 'USED', 'USEFUL', 'USER', 'USUAL', 'USUALLY', 'UTILITY', 'VACANT',
            'VAGUE', 'VALID', 'VALUE', 'VAN', 'VANISH', 'VARIABLE', 'VARIETY', 'VARIOUS',
            'VAST', 'VAULT', 'VEHICLE', 'VENDOR', 'VENTURE', 'VERIFY', 'VERSION', 'VERSUS',
            'VERY', 'VETERAN', 'VIA', 'VICE', 'VICTORY', 'VIDEO', 'VIEW', 'VIGOR', 'VILLAGE',
            'VIOLENCE', 'VIOLENT', 'VIRAL', 'VIRTUAL', 'VIRUS', 'VISIT', 'VISITOR', 'VISUAL',
            'VITAL', 'VIVID', 'VOCAL', 'VOICE', 'VOID', 'VOLUME', 'VOLUNTEER', 'VOTE', 'VOTER',
            'VOYAGE', 'WAGE', 'WAIT', 'WAKE', 'WALK', 'WALL', 'WANDER', 'WANT', 'WAR', 'WARD',
            'WARM', 'WARN', 'WARRANT', 'WARRIOR', 'WASH', 'WASTE', 'WATCH', 'WATER', 'WAVE',
            'WAY', 'WEAK', 'WEALTH', 'WEAPON', 'WEAR', 'WEATHER', 'WEB', 'WEEK', 'WEEKEND',
            'WEIGH', 'WEIGHT', 'WEIRD', 'WELCOME', 'WELFARE', 'WELL', 'WEST', 'WET', 'WHAT',
            'WHEAT', 'WHEEL', 'WHEN', 'WHERE', 'WHETHER', 'WHICH', 'WHILE', 'WHIP', 'WHITE',
            'WHO', 'WHOLE', 'WHOM', 'WHOSE', 'WHY', 'WIDE', 'WIFE', 'WILD', 'WILL', 'WIN',
            'WIND', 'WINDOW', 'WINE', 'WING', 'WINNER', 'WINTER', 'WIRE', 'WISDOM', 'WISE',
            'WISH', 'WITH', 'WITHIN', 'WITHOUT', 'WITNESS', 'WOLF', 'WOMAN', 'WONDER', 'WOOD',
            'WOOL', 'WORD', 'WORK', 'WORKER', 'WORLD', 'WORRY', 'WORSE', 'WORST', 'WORTH',
            'WOULD', 'WOUND', 'WRAP', 'WRECK', 'WRESTLE', 'WRITE', 'WRITER', 'WRITING', 'WRONG',
            'YARD', 'YEAR', 'YELLOW', 'YES', 'YESTERDAY', 'YET', 'YIELD', 'YOU', 'YOUNG',
            'YOUR', 'YOURS', 'YOURSELF', 'YOUTH', 'ZERO', 'ZONE'
        }
        
        # PRIORITY 1: Extract tokens from article tags (preferred method)
        tokens_found_via_tags = {}  # {token: [occurrences]} - tokens found via tags
        problematic_token_tags = []  # List of problematic token tags that need database fixes
        for news_item in all_news:
            tags = news_item.get('tags', [])
            headline = news_item.get('headline', '')
            for tag in tags:
                if tag.get('is_token_tag') and tag.get('token'):
                    token_data = tag['token']
                    symbol = token_data.get('symbol', '')
                    name = token_data.get('name', '')
                    
                    # Check for problematic token tags
                    symbol_upper = symbol.upper().replace('$', '').strip() if symbol else ''
                    name_upper = name.upper().strip() if name else ''
                    
                    # Problematic: symbol becomes empty after processing, or both symbol and name are missing/empty
                    is_problematic = False
                    problem_reason = None
                    
                    if symbol and not symbol_upper:
                        # Symbol exists but becomes empty after processing (e.g., symbol is just "$")
                        is_problematic = True
                        problem_reason = f"Symbol '{symbol}' becomes empty after processing"
                    elif not symbol and not name_upper:
                        # No symbol and no valid name
                        is_problematic = True
                        problem_reason = "Missing both symbol and name"
                    elif symbol and not symbol_upper and not name_upper:
                        # Symbol becomes empty and no valid name to fall back to
                        is_problematic = True
                        problem_reason = f"Symbol '{symbol}' becomes empty and no valid name"
                    
                    if is_problematic:
                        problematic_token_tags.append({
                            'article_id': news_item.get('id'),
                            'headline': headline,
                            'url': news_item.get('url', ''),
                            'token_data': token_data,
                            'problem': problem_reason
                        })
                        continue  # Skip this problematic tag
                    
                    # Use symbol as primary identifier, fallback to name
                    if symbol_upper:
                        if symbol_upper not in tokens_found_via_tags:
                            tokens_found_via_tags[symbol_upper] = []
                        tokens_found_via_tags[symbol_upper].append({
                            'headline': headline,
                            'id': news_item.get('id'),
                            'url': news_item.get('url', ''),
                            'format': 'TAG',
                            'token_name': name
                        })
                    elif name_upper:
                        # No valid symbol, use name instead
                        if name_upper not in tokens_found_via_tags:
                            tokens_found_via_tags[name_upper] = []
                        tokens_found_via_tags[name_upper].append({
                            'headline': headline,
                            'id': news_item.get('id'),
                            'url': news_item.get('url', ''),
                            'format': 'TAG',
                            'token_name': name
                        })
        
        # Find potential tokens in headlines (secondary method)
        potential_tokens = {}  # {token: [occurrences]}
        tokens_found_in_headlines = {}  # {token: [occurrences]} - tokens found in headline text
        headlines_checked = 0
        
        for news_item in all_news:
            headline = news_item.get('headline', '')
            if not headline:
                continue
            
            headlines_checked += 1
            
            # Debug: Show raw headline data for specific token
            if debug_token and debug_token in headline.upper():
                self.stdout.write('\n' + '='*80)
                self.stdout.write(self.style.SUCCESS(f'🔍 DEBUG: Headline containing "{debug_token}"'))
                self.stdout.write('='*80)
                self.stdout.write(f'\nRaw headline: {headline}')
                self.stdout.write(f'\nFull news item JSON:\n')
                self.stdout.write(json.dumps(news_item, indent=2))
                self.stdout.write('\n' + '='*80 + '\n')
            
            # Priority 1: Find $TOKEN format (most reliable)
            dollar_matches = dollar_token_pattern.findall(headline)
            for candidate in dollar_matches:
                candidate_upper = candidate.upper()
                
                # Debug specific token matching
                if debug_token and candidate_upper == debug_token:
                    self.stdout.write(f'\n🔍 DEBUG: Found ${candidate_upper} in headline')
                    self.stdout.write(f'  Headline: {headline}')
                    self.stdout.write(f'  Candidate (from $TOKEN): {candidate_upper}')
                    self.stdout.write(f'  In token_symbols? {candidate_upper in token_symbols}')
                    self.stdout.write(f'  Also checking ${candidate_upper}: ${candidate_upper} in token_symbols?')
                    self.stdout.write(f'  In token_names? {candidate_upper in token_names}')
                    self.stdout.write(f'  token_symbols sample: {sorted(list(token_symbols))[:20]}')
                    
                    # Check both with and without $ prefix
                    matching_symbols = []
                    for t in tokens:
                        t_symbol = t.get('symbol', '').upper()
                        if t_symbol == candidate_upper or t_symbol == f'${candidate_upper}':
                            matching_symbols.append(t)
                    
                    # Also check tags
                    tags = news_item.get('tags', [])
                    tag_tokens = []
                    for tag in tags:
                        if tag.get('is_token_tag') and tag.get('token'):
                            token_data = tag['token']
                            t_symbol = token_data.get('symbol', '').upper()
                            if t_symbol == candidate_upper or t_symbol == f'${candidate_upper}':
                                tag_tokens.append(token_data)
                    
                    if matching_symbols:
                        self.stdout.write(f'  Matching token from API: {json.dumps(matching_symbols[0], indent=2)}')
                    if tag_tokens:
                        self.stdout.write(f'  Matching token from tags: {json.dumps(tag_tokens[0], indent=2)}')
                    if not matching_symbols and not tag_tokens:
                        self.stdout.write(f'  ⚠️  No matching token found!')
                
                if candidate_upper in token_symbols or candidate_upper in token_names:
                    # This token IS tracked - record it
                    if candidate_upper not in tokens_found_in_headlines:
                        tokens_found_in_headlines[candidate_upper] = []
                    tokens_found_in_headlines[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': '$TOKEN'
                    })
                elif (candidate_upper not in excluded_words and
                      len(candidate_upper) >= 3):
                    # Potential missing token with $ prefix (high confidence)
                    if candidate_upper not in potential_tokens:
                        potential_tokens[candidate_upper] = []
                    potential_tokens[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': '$TOKEN',
                        'confidence': 'high'
                    })
            
            # Priority 2: Find uppercase words (3-10 chars)
            uppercase_matches = uppercase_token_pattern.findall(headline)
            for candidate in uppercase_matches:
                candidate_upper = candidate.upper()
                # Skip if already processed as $TOKEN
                if candidate_upper in [m.upper() for m in dollar_matches]:
                    continue
                
                # Debug specific token matching
                if debug_token and candidate_upper == debug_token:
                    self.stdout.write(f'\n🔍 DEBUG: Found {candidate_upper} (uppercase) in headline')
                    self.stdout.write(f'  Headline: {headline}')
                    self.stdout.write(f'  In token_symbols? {candidate_upper in token_symbols}')
                    self.stdout.write(f'  In token_names? {candidate_upper in token_names}')
                    if candidate_upper in token_symbols:
                        matching = [t for t in tokens if t.get('symbol', '').upper() == candidate_upper]
                        self.stdout.write(f'  Matching token: {json.dumps(matching[0] if matching else {}, indent=2)}')
                    elif candidate_upper in token_names:
                        matching = [t for t in tokens if t.get('name', '').upper() == candidate_upper]
                        self.stdout.write(f'  Matching token: {json.dumps(matching[0] if matching else {}, indent=2)}')
                
                if candidate_upper in token_symbols or candidate_upper in token_names:
                    # This token IS tracked
                    if candidate_upper not in tokens_found_in_headlines:
                        tokens_found_in_headlines[candidate_upper] = []
                    tokens_found_in_headlines[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': 'UPPERCASE'
                    })
                elif (candidate_upper not in excluded_words and
                      candidate_upper not in token_symbols and
                      candidate_upper not in token_names and
                      len(candidate_upper) >= 3):
                    # Potential missing token
                    if candidate_upper not in potential_tokens:
                        potential_tokens[candidate_upper] = []
                    potential_tokens[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': 'UPPERCASE',
                        'confidence': 'medium'
                    })
            
            # Priority 3: Find tokens with context (token/coin/stablecoin)
            context_matches = context_token_pattern.findall(headline)
            for candidate in context_matches:
                candidate_upper = candidate.upper()
                if candidate_upper in token_symbols or candidate_upper in token_names:
                    # This token IS tracked
                    if candidate_upper not in tokens_found_in_headlines:
                        tokens_found_in_headlines[candidate_upper] = []
                    tokens_found_in_headlines[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': 'CONTEXT'
                    })
                elif (candidate_upper not in excluded_words and
                      candidate_upper not in token_symbols and
                      candidate_upper not in token_names and
                      len(candidate_upper) >= 3):
                    # Potential missing token with context (high confidence)
                    if candidate_upper not in potential_tokens:
                        potential_tokens[candidate_upper] = []
                    potential_tokens[candidate_upper].append({
                        'headline': headline,
                        'id': news_item.get('id'),
                        'url': news_item.get('url', ''),
                        'format': 'CONTEXT',
                        'confidence': 'high'
                    })
        
        # Validate readiness for each article
        readiness_results = []
        for news_item in all_news:
            headline = news_item.get('headline', '')
            if not headline:
                continue
            
            # Check if article has token tags
            tags = news_item.get('tags', [])
            token_tags = [tag for tag in tags if tag.get('is_token_tag') and tag.get('token')]
            has_token_tags = len(token_tags) > 0
            
            # Extract tickers from token tags
            tickers_from_tags = []
            for tag in token_tags:
                token_data = tag.get('token', {})
                symbol = token_data.get('symbol', '').strip()
                if symbol and symbol != '$' and len(symbol.replace('$', '')) > 0:
                    clean_symbol = symbol.upper().replace('$', '').strip()
                    if clean_symbol:
                        tickers_from_tags.append(clean_symbol)
            
            # Check if headline mentions tracked tokens
            mentions_tracked_tokens = False
            headline_upper = headline.upper()
            for token_symbol in token_symbols:
                if token_symbol in headline_upper or f'${token_symbol}' in headline_upper:
                    mentions_tracked_tokens = True
                    break
            
            # Determine readiness
            ready = has_token_tags or mentions_tracked_tokens
            
            readiness_results.append({
                'id': news_item.get('id'),
                'headline': headline,
                'url': news_item.get('url', ''),
                'ready': ready,
                'has_token_tags': has_token_tags,
                'tickers_from_tags': tickers_from_tags,
                'mentions_tracked_tokens': mentions_tracked_tokens
            })
        
        # Merge tokens found via tags with tokens found in headlines (tags take priority)
        # Tags are the preferred source, so we combine them but prioritize tag format
        all_tracked_tokens = {}
        for token, occurrences in tokens_found_via_tags.items():
            all_tracked_tokens[token] = occurrences
        # Add headline-found tokens that weren't already found via tags
        for token, occurrences in tokens_found_in_headlines.items():
            if token not in all_tracked_tokens:
                all_tracked_tokens[token] = occurrences
            else:
                # Merge but keep tag format as primary
                all_tracked_tokens[token].extend(occurrences)
        
        # Report results
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'📊 Review Summary'))
        self.stdout.write('='*80)
        self.stdout.write(f'Headlines checked: {headlines_checked}')
        self.stdout.write(f'Tokens found via tags (preferred): {len(tokens_found_via_tags)}')
        self.stdout.write(f'Tokens found in headline text: {len(tokens_found_in_headlines)}')
        self.stdout.write(f'Total tracked tokens found: {len(all_tracked_tokens)}')
        self.stdout.write(f'Potential missing tokens found: {len(potential_tokens)}')
        if problematic_token_tags:
            self.stdout.write(self.style.ERROR(f'🚨 Problematic token tags (need DB fix): {len(problematic_token_tags)}'))
        
        # Readiness summary
        ready_count = sum(1 for r in readiness_results if r['ready'])
        not_ready_count = len(readiness_results) - ready_count
        self.stdout.write(f'\n📋 Article Readiness:')
        self.stdout.write(self.style.SUCCESS(f'  ✓ Ready to process: {ready_count}'))
        if not_ready_count > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Needs attention: {not_ready_count}'))
        self.stdout.write('')
        
        # Show problematic token tags that need database fixes
        if problematic_token_tags:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.ERROR('🚨 PROBLEMATIC TOKEN TAGS (Database Fix Needed)'))
            self.stdout.write('='*80)
            self.stdout.write(self.style.ERROR(f'\nFound {len(problematic_token_tags)} article(s) with problematic token tags:\n'))
            self.stdout.write(self.style.ERROR('These tags have invalid symbols/names and need to be corrected in the database.\n'))
            
            for i, problem in enumerate(problematic_token_tags, 1):
                self.stdout.write(f'\n{i}. Article ID: {problem["article_id"]}')
                self.stdout.write(f'   Headline: {problem["headline"][:75]}...')
                self.stdout.write(f'   URL: {problem["url"][:75]}...')
                self.stdout.write(self.style.ERROR(f'   ⚠️  Problem: {problem["problem"]}'))
                self.stdout.write(f'   Raw token data:')
                self.stdout.write(json.dumps(problem['token_data'], indent=6))
                self.stdout.write('')
            
            self.stdout.write('='*80 + '\n')
        
        # Show tokens that ARE tracked (prioritize tags)
        if all_tracked_tokens:
            self.stdout.write(self.style.SUCCESS('\n✅ Tokens Found (Already Tracked):\n'))
            
            # Sort by frequency, but prioritize tokens found via tags
            sorted_found = sorted(
                all_tracked_tokens.items(),
                key=lambda x: (
                    'TAG' not in [occ.get('format', '') for occ in x[1]],  # Tags first
                    -len(x[1])  # Then by frequency
                )
            )
            
            for token, occurrences in sorted_found[:20]:  # Show top 20
                count = len(occurrences)
                formats = set(occ.get('format', '') for occ in occurrences)
                # Show TAG format prominently
                if 'TAG' in formats:
                    format_str = 'TAG' + (f', {", ".join(f for f in formats if f != "TAG")}' if len(formats) > 1 else '')
                else:
                    format_str = ', '.join(formats)
                self.stdout.write(f'  ✓ {token} ({count}x) [{format_str}]')
                if verbose and occurrences:
                    # Prefer showing tag-based occurrence
                    tag_occ = next((occ for occ in occurrences if occ.get('format') == 'TAG'), occurrences[0])
                    self.stdout.write(f'    Example: {tag_occ["headline"][:75]}...')
            
            if len(sorted_found) > 20:
                self.stdout.write(f'  ... and {len(sorted_found) - 20} more tracked tokens\n')
            else:
                self.stdout.write('')
        
        # Show potential missing tokens, prioritized by confidence
        if potential_tokens:
            # Separate by confidence level
            high_confidence = {}
            medium_confidence = {}
            
            for token, occurrences in potential_tokens.items():
                # Check if any occurrence has high confidence
                has_high = any(occ.get('confidence') == 'high' for occ in occurrences)
                if has_high:
                    high_confidence[token] = occurrences
                else:
                    medium_confidence[token] = occurrences
            
            # Show high confidence first
            if high_confidence:
                self.stdout.write(self.style.WARNING('\n⚠️  High Confidence - Potential Missing Tokens:\n'))
                self.stdout.write(self.style.WARNING('   (Tokens with $ prefix or explicit token/coin context)\n'))
                
                sorted_high = sorted(
                    high_confidence.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
                
                for token, occurrences in sorted_high:
                    count = len(occurrences)
                    formats = set(occ.get('format', '') for occ in occurrences)
                    format_str = ', '.join(formats)
                    self.stdout.write(f'\n  🔸 {token} (mentioned {count} time{"s" if count > 1 else ""}) [{format_str}]')
                    
                    if verbose:
                        for occ in occurrences[:3]:  # Show first 3
                            self.stdout.write(f'     • {occ["headline"][:75]}...')
                        if len(occurrences) > 3:
                            self.stdout.write(f'     ... and {len(occurrences) - 3} more')
                    else:
                        # Show just first occurrence
                        self.stdout.write(f'     Example: {occurrences[0]["headline"][:75]}...')
            
            # Show medium confidence (but limit to most frequent)
            if medium_confidence:
                self.stdout.write(self.style.WARNING('\n\n⚠️  Medium Confidence - Potential Missing Tokens:\n'))
                self.stdout.write(self.style.WARNING('   (Uppercase words that might be tokens - review carefully)\n'))
                
                sorted_medium = sorted(
                    medium_confidence.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
                
                # Only show top 15 medium confidence to reduce noise
                for token, occurrences in sorted_medium[:15]:
                    count = len(occurrences)
                    self.stdout.write(f'\n  🔸 {token} ({count}x)')
                    if verbose:
                        self.stdout.write(f'     Example: {occurrences[0]["headline"][:75]}...')
                
                if len(sorted_medium) > 15:
                    self.stdout.write(f'\n  ... and {len(sorted_medium) - 15} more (use --verbose to see all)')
            
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('\n💡 Suggestion: Focus on "High Confidence" tokens first.'))
            self.stdout.write('   Review "Medium Confidence" carefully - many are false positives.\n')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ No potential missing tokens detected!\n'))
        
        # Show readiness details
        if verbose or show_readiness or not_ready_count > 0:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('📋 Article Readiness Details'))
            self.stdout.write('='*80 + '\n')
            
            # Sort by readiness (not ready first)
            sorted_readiness = sorted(readiness_results, key=lambda x: (x['ready'], -x['id']), reverse=False)
            
            for result in sorted_readiness:
                status_icon = '✅' if result['ready'] else '❌'
                self.stdout.write(f'\n{status_icon} [{result["id"]}] {result["headline"][:70]}...')
                
                if result['has_token_tags']:
                    if result['tickers_from_tags']:
                        tickers_str = ', '.join([f'${t}' for t in result['tickers_from_tags']])
                        self.stdout.write(self.style.SUCCESS(f'   ✓ Has token tags: {tickers_str}'))
                    else:
                        self.stdout.write(self.style.WARNING('   ⚠️  Has token tags but no valid ticker symbols'))
                elif result['mentions_tracked_tokens']:
                    self.stdout.write(self.style.SUCCESS('   ✓ Mentions tracked tokens in headline'))
                else:
                    self.stdout.write(self.style.WARNING('   ⚠️  No token tags and no tracked tokens mentioned'))
                
                if verbose:
                    self.stdout.write(f'   URL: {result["url"][:80]}...')
            
            self.stdout.write('\n' + '='*80 + '\n')
