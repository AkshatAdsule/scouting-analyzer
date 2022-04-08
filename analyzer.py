import firebase_admin
import requests
import argparse
from dotenv import load_dotenv
import os
from firebase_admin import credentials, firestore

load_dotenv()
cred = credentials.Certificate("creds.json")
TBA_AUTH_HEADER = {'X-TBA-Auth-Key': os.environ["TBA_AUTH_KEY"]}
CSV_HEADER="team,quoted accuracy,auton balls,auton routine,using bad falcons,climb levels,drivebase type,driver experience,features,average low hub shots,average high hub shots,scouted accuracy,average climb level,average pieces scored,high hub ratio,average points scored,total matches"

firebase_admin.initialize_app(cred)
db = firestore.client()

teams_ref = db.collection(u"2022/info/teams")
docs = teams_ref.stream()

def get_teams_in_event(eventcode):
	url = f"https://www.thebluealliance.com/api/v3/event/{eventcode}/teams/simple"
	try:
		r = requests.get(url, headers=TBA_AUTH_HEADER)
	except:
		print("TBA get all teams failed")
		return []
	r_json = r.json()
	all_teams = []
	for team_info in r_json:
		team_key = team_info['key']
		team_num = team_key[3:]
		all_teams.append(team_num)
	return all_teams

def get_team_doc(team):
	team_ref = teams_ref.document(str(team))
	team_doc = team_ref.get()
	if not team_doc.exists:
		return None
	return team_doc.to_dict()

def get_all_teams_data(teams):
	all_teams_data = []
	for team in teams:
		doc = get_team_doc(team)
		if doc is None:
			print(f"Could not find scouting data for {team}")
		else:
			print(f"Got scouting data for team {team}")
			doc["team_name"] = team
			add_match_scouting_data(team, doc)
			all_teams_data.append(doc)
	return all_teams_data


def add_match_scouting_data(team, data):
	matches = teams_ref.document(team).collection("matches").stream()

	# overall data
	total_shots = 0
	successful_shots = 0
	high_hub_shots = 0
	low_hub_shots = 0
	total_match_points = 0
	total_matches = 0
	total_climb_levels = 0
	for match in matches:
		match_points = 0
		total_matches+=1
		has_already_climbed = False
		match_data = match.to_dict()
		print(f"Parsing {match_data['matchType']}{match.id} for {team}")
		for action in match_data["actions"]:
			action_type = action["actionType"]
			if action_type == "SHOT_UPPER":
				match_points+=2
				high_hub_shots+=1
				successful_shots+=1
				total_shots+=1
			if action_type == "MISSED_UPPER":
				high_hub_shots+=1
				total_shots+=1
			if action_type == "SHOT_LOWER":
				match_points+=1
				low_hub_shots+=1
				successful_shots+=1
				total_shots+=1
			if action_type == "MISSED_LOWER":
				low_hub_shots+=1
				total_shots+=1
			if "CLIMB" in action_type and not has_already_climbed:
				has_already_climbed = True
				if "LOW" in action_type:
					match_points+=4
					total_climb_levels+=1
				elif "MID" in action_type:
					match_points+=6
					total_climb_levels+=2
				elif "HIGH" in action_type:
					match_points+=10
					total_climb_levels+=3
				elif "TRAVERSAL" in action_type:
					match_points+=15
					total_climb_levels+=4
		total_match_points+=match_points

	if total_matches > 0:
		data["total_matches"] = total_matches
		data["avg_low_hub_shots"] = low_hub_shots / total_matches
		data["avg_high_hub_shots"] = high_hub_shots / total_matches
		data["average_points_scored"] = total_match_points / total_matches
		data["average_pieces_scored"] = successful_shots / total_matches
		data["average_climb_level"] = total_climb_levels / total_matches
	else:
		data["total_matches"] = 0
	if total_shots == 0:
		data["high_hub_ratio"] = 1
		data["scouted_accuracy"] = 0
	else:
		data["scouted_accuracy"] = successful_shots / total_shots
		data["high_hub_ratio"] = high_hub_shots / total_shots

def generate_csv(all_teams_data, filename):
	with open(filename, 'a') as file:
		file.truncate(0)
		file.write(CSV_HEADER + '\n')
		for team_data in all_teams_data:
			try:
				csv_line = f"{team_data['team_name']},{team_data['accuracy'].replace(',',';')},{team_data['autonBalls']},{team_data['autonRoutine'].replace(',',';')},{team_data['badFalcons']},{str(team_data['climbLocations']).replace(',', ' and ')},{team_data['drivebaseType']},{team_data['driverExperience'].replace(',',';')},{team_data['features'].replace(',',';')},{team_data['avg_low_hub_shots']},{team_data['avg_high_hub_shots']},{team_data['scouted_accuracy']},{team_data['average_climb_level']},{team_data['average_pieces_scored']},{team_data['high_hub_ratio']},{team_data['average_pieces_scored']},{team_data['total_matches']}\n"
				file.write(csv_line)
			except KeyError:
				print(f"Invalid data for: {team_data['team_name']}")
		file.close()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Analyze results from Match Scouting")
	parser.add_argument("eventcode")
	args = parser.parse_args()
	teams = get_teams_in_event(args.eventcode)
	all_teams_data =  get_all_teams_data(teams)
	generate_csv(all_teams_data, args.eventcode + ".csv")
