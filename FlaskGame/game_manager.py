import time

# inits
# gets
# processing actions
# actions logic
# actions availability conditions
# helper methods

class GameManager:
    def __init__(self, locations_config, sabotage_cd, bless_cd, stun_duration, jam_cd, capture_time=60):
        self.locations_config = locations_config
        self.capture_time = capture_time
        self.sabotage_cd = sabotage_cd
        self.bless_cd = bless_cd
        self.stun_duration = stun_duration
        self.jam_cd = jam_cd
        self.rooms = {}
        self.player_states = {}
        self.active_votes = {}

    def initialize_room(self, room_id):
        initial_state = {}
        for k, v in self.locations_config.items():
            initial_state[k] = {
                "id": k,
                "name": v["name"],
                "owner": v.get("default_owner", "Neutral"),
                "adj": v["adj"],
                "type": v["type"],
                "x": v["x"],
                "y": v["y"],
                "capture_in_progress": False,
                "capturing_team": None,
                "start_time": 0,
                "capturer_nick": None,
                "is_trapped": False,
                "is_blessed": False,
                "last_jam_time": 0
            }
        self.rooms[room_id] = initial_state
        self.player_states[room_id] = {}

    def get_state(self, room_id):
        return self.rooms.get(room_id)

    def _get_player_data(self, room_id, nick):
        if nick not in self.player_states[room_id]:
            self.player_states[room_id][nick] = {}
        return self.player_states[room_id][nick]

    def register_player(self, room_id, nick, team):
        if room_id not in self.player_states:
            self.player_states[room_id] = {}
        
        self.player_states[room_id][nick] = {
            "team": team,
            "at_loc": None,
            "last_scan": 0,
            "stun_until": {},
            "last_ability": 0,
            "voted_out" : False
        }

    def _get_action_map(self):
        return {
            "START_RITUAL": self._do_start_ritual,
            "STOP_RITUAL": self._do_stop_ritual,
            "FINALIZE_RITUAL": self._do_finalize_ritual,
            "SABOTAGE": self._do_sabotage,
            "BLESS": self._do_bless,
            "CURSE": self._do_curse,
        }

    def process_action(self, room_id, shrine_id, action, player):
        state = self.rooms[room_id][shrine_id]
        p_data = self._get_player_data(room_id, player['nick'])
        
        action_map = self._get_action_map()
        
        if action in action_map:
            return action_map[action](state, p_data, player)
        
        return [f"Unknown action: {action}"] #just in case

    # actions 

    def _do_start_ritual(self, state, p_data, player):
        if state.get('is_trapped'):
            state['is_trapped'] = False
            p_data['stun_until'][state['id']] = time.time() + self.stun_duration
            return [f" HEXED! {player['nick']} triggered a trap! Stunned for {self.stun_duration}s."]
        
        
        start_delay = 20 if (state.get('is_blessed') and player['team'] == 'Heretics') else 0
        
        state.update({
            'capture_in_progress': True,
            'capturing_team': player['team'],
            'start_time': time.time() + start_delay,
            'capturer_nick': player['nick']
        })
        msg = "Ritual started!" + (" (Delayed by Blessing)" if start_delay else "")
        return [msg]

    def _do_finalize_ritual(self, state, p_data, player):
        state.update({
            'capture_in_progress': False,
            'owner': player['team'],
            'capturing_team': None,
        })
        return [f" {state['name']} captured by {player['team']}!"]

    def _do_bless(self,state, p_data, player):
        state['is_blessed'] = True
        p_data['last_ability'] = time.time() 
        
        return [f"Someone has blessed the {state['name']}! Rituals here will now proceed faster."]

    def _do_sabotage(self, state, p_data, player):
        if state.get('is_blessed'):
            state['is_blessed'] = False
            logs = [f" Someone desecrated the shrine! The blessing has been extinguished."]
        else:
            state['is_trapped'] = True
            logs = [f"Someone has placed a dark trap on a shrine!"]
        
        p_data['last_ability'] = time.time()
        return logs

    def _do_stop_ritual(self, state, p_data, player):
        state['capture_in_progress'] = False
        return [f"Someone interrupted the ritual at {state['name']}"]
    
    def _do_curse(self, room_id, target_nick, scanner_nick, shrine_id):
        target_data = self._get_player_data(room_id, target_nick)
        if target_data:
            target_data["stun_until"][shrine_id] = time.time() + self.stun_duration
            return [f"Someone cast a shadow! {target_nick} has been cursed!"]

    # get actions

    def get_available_actions(self, room_id, shrine_id, nick):
        state = self.rooms[room_id][shrine_id]
        p_data = self._get_player_data(room_id, nick)
        user_team = p_data["team"]
        now = time.time()
        actions = []

        if p_data['voted_out']:
            return ["SPECTATOR_MODE"]
    
        if state['type'] == 'jammer':
            elapsed = now - state.get('last_jam_time', 0)
    
            if elapsed < self.jam_cd:
                remaining = int(self.jam_cd - elapsed)
                return [f"JAMMER RECHARGING ({remaining}s)"]
            return ["JAM_SIGNALS"]

        if now < p_data['stun_until'].get(shrine_id, 0):
            return [f"STUNNED ({int(p_data['stun_until'].get(shrine_id, 0) - now)}s)"]

        targets = self._get_targets_at_location(room_id, shrine_id, nick)
        
        for t_nick in targets:
            t_data = self._get_player_data(room_id, t_nick)
            if not t_data.get('voted_out'):
                actions.append(f"VOTE_FOR_{t_nick}")
           
        if user_team == "Heretics":
            targets = self._get_targets_at_location(room_id, shrine_id, nick)
            for target_nick in targets:
                actions.append(f"CURSE_{target_nick}")
        
        if state['capture_in_progress']:
            if state['capturing_team'] != user_team:
                actions.append("STOP_RITUAL")
            elif state['capturing_team'] == user_team:
                if self._is_ritual_ready(state) and state.get('capturer_nick') != nick:
                    actions.append("FINALIZE_RITUAL")
                else:
                    req = self.capture_time * (0.5 if (state.get('is_blessed') and user_team == "Sentinels") else 1.0)
                    remaining = int(req - (now - state['start_time']))
                    if remaining <= 0 and state.get('capturer_nick') == nick:
                        actions.append("WAITING FOR ALLY TO FINALIZE")
                    else:
                        actions.append(f"RITUAL IN PROGRESS ({max(0, remaining)}s)")
            return actions

       
        actions += self._get_team_abilities(state, p_data, now)
        
        if state['owner'] != user_team and self._is_adjacent(room_id, state, user_team):
            actions.append("START_RITUAL")
        return actions

    # aditional helper methods 

    def _is_ritual_ready(self, state):
        elapsed = time.time() - state['start_time']
        required = self.capture_time * (0.5 if (state.get('is_blessed') and state['capturing_team'] == "Sentinels") else 1.0)
        return elapsed >= required


    def _get_team_abilities(self, state, p_data, now):
        abs_list = []
        team = p_data["team"]
        cd = self.sabotage_cd if team == "Heretics" else self.bless_cd
        can_act = (now - p_data.get("last_ability", 0)) > cd
        
        if team == "Heretics" and not state['is_trapped']:
            abs_list.append("SABOTAGE" if can_act else f"SABOTAGE CD ({int(cd - (now-p_data['last_ability']))}s)")
        
        if team == "Sentinels" and state['owner'] == "Sentinels" and not state['is_blessed']:
            abs_list.append("BLESS" if can_act else f"BLESS CD ({int(cd - (now-p_data['last_ability']))}s)")
            
        return abs_list

    def _is_adjacent(self, room_id, state, user_team):
        shrine_neighbors = state.get('adj', [])
        room_state = self.rooms.get(room_id, {})

        for neighbor_id in shrine_neighbors:
            neighbor_data = room_state.get(neighbor_id)
            if neighbor_data and neighbor_data.get('owner') == user_team:
                return True
                
        return False

    def _get_targets_at_location(self, room_id, shrine_id, scanner_nick):
        targets = []
        now = time.time()
        room_players = self.player_states.get(room_id, {})
        for nick, data in room_players.items():     
            if (data.get("at_loc") == shrine_id and 
                nick != scanner_nick and 
                (now - data.get("last_scan", 0)) < self.capture_time):
                targets.append(nick)
        return targets
    def check_winner(self, room_id):
        shrine_count = 0
        ownership = {"Sentinels": 0, "Heretics": 0}
        
        room_state = self.rooms.get(room_id, {})
        for loc_id, data in room_state.items():
            # ignore starging points for now
            if self.locations_config[loc_id]["type"] == "shrine":
                shrine_count += 1
                if data["owner"] in ownership:
                    ownership[data["owner"]] += 1
        
        # wining condition: capture all execpt one tbd
        win_threshold = shrine_count - 1
        
        for team, count in ownership.items():
            if count >= win_threshold:
                return team
        return None

    
    def clear_room_data(self, room_id):
        if room_id in self.rooms:
            del self.rooms[room_id]
        if room_id in self.player_states:
            del self.player_states[room_id]

    def start_council(self, room_id, target, requester):
        
        all_players = self.player_states.get(room_id, {})
        voters_eligible = [
            p for p in all_players 
            if not all_players[p].get('voted_out') and p != target
        ]
        
        self.active_votes[room_id] = {
            'target': target,
            'votes': {requester: True}, # still recieves prompt to vote that can change it eh
            'total_needed': len(voters_eligible)
        }
        return True

    def cast_vote(self, room_id, voter, choice):
        
        if room_id not in self.active_votes:
            return None

        vote_data = self.active_votes[room_id]
        vote_data['votes'][voter] = choice
        
        if len(vote_data['votes']) >= vote_data['total_needed']:
            yes_votes = sum(1 for v in vote_data['votes'].values() if v)
            
            result = {
                'complete': True,
                'target': vote_data['target'],
                'success': yes_votes > (vote_data['total_needed'] / 2)
            }
            
            del self.active_votes[room_id]
            return result
            
        return {'complete': False}