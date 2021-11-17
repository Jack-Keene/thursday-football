from flask import Flask, render_template, request, flash, session
from flask.helpers import url_for
from flask.scaffold import F, find_package
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import redirect
from sqlalchemy.sql import func
from functools import wraps
from passlib.hash import sha256_crypt


app = Flask(__name__)

# app.config['DEBUG'] = True
# app.config['ENV'] = 'development'

ENV = 'prod'

app.secret_key="secret_key"

if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:m4rt9r6H@localhost/football'
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://gsgjwkikyldgen:296c51725ee925ce8f31f5a76e91620ccb05430d2477ddef88264932938c3b5e@ec2-3-208-157-78.compute-1.amazonaws.com:5432/d5sgut048e16dp'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Players(db.Model):
    __tablename__='players'
    player_id = db.Column(db.Integer, primary_key=True, nullable=False)
    team_id =db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=True)
    first_name = db.Column(db.String(length=100), nullable=False)
    last_name = db.Column(db.String(length=100), nullable=False)
    username = db.Column(db.String(length=100), unique=True, nullable=True)
    hashed = db.Column(db.String(length=255), nullable=True)
    squad_number = db.Column(db.Integer, nullable=True)
    position = db.Column(db.String(length=100), nullable=True)
    type = db.Column(db.String(length=100), nullable=False)

    def __init__(self, team_id, first_name, last_name, username, hashed, squad_number, position):
        self.team_id = team_id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.hashed = hashed
        self.squad_number = squad_number
        self.position = position
        self.type = 'Player'

class Teams(db.Model):
    __tablename__='teams'
    team_id = db.Column(db.Integer, primary_key=True, nullable=False)
    team_name = db.Column(db.String(length=255), nullable=False)

    def __init__(self,  team_name):
        self.team_name = team_name

class Fixture(db.Model):
    __tablename__='fixtures'
    fixture_id = db.Column(db.Integer, primary_key=True, nullable=False)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.league_id'), nullable=False)
    date = db.Column(db.Date(), nullable=True)
    time = db.Column(db.String(), nullable=True)
    played = db.Column(db.Boolean(), nullable=False)
    match_report = db.Column(db.Text, nullable=True)

    def __init__(self, league_id, date, time, played, match_report):
        self.league_id = league_id
        self.date = date
        self.time = time
        self.played = played
        self.match_report = match_report

class FixtureDetails(db.Model):
    __tablename__='fixture_details'
    detail_id = db.Column(db.Integer, primary_key=True, nullable=False)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.fixture_id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=False)
    home = db.Column(db.Boolean(), nullable=False)
    goals = db.Column(db.Integer(), nullable=True)
    goals_against = db.Column(db.Integer(), nullable=True)
    result = db.Column(db.String(), nullable=True)
    points = db.Column(db.Integer(), nullable=True)


    def __init__(self, fixture_id, team_id, home, goals, goals_against, points):
        self.fixture_id=fixture_id
        self.team_id=team_id
        self.home=home
        self.goals=goals
        self.goals_against = goals_against
        self.points = points

class Leagues(db.Model):
    __tablename__='leagues'
    league_id = db.Column(db.Integer, primary_key=True, nullable=False)
    league_name = db.Column(db.String(length=255), nullable=False)

    def __init__(self, league_name):
        self.league_name = league_name

class Stats(db.Model):
    __tablename__='stats'
    stat_id = db.Column(db.Integer, primary_key=True, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.player_id'), nullable=True)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.fixture_id'), nullable=False)
    stat_type = db.Column(db.String(), nullable=False)
    fp_points = db.Column(db.Integer, nullable=True)

    def __init__(self, player_id, fixture_id, stat_type, fp_points):
        self.player_id =player_id
        self.fixture_id = fixture_id
        self.stat_type = stat_type
        self.fp_points = fp_points

def login_required(access=0):
    def wrapper(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if 'access_level' not in session.keys():
                return redirect('/')
            if session['access_level'] >= access:
                return f(*args, **kwargs)
            else:
                return redirect('/')
        return wrap
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():

    ACCESS = {'guest': 0,
            'Player': 1,
            'Admin': 2,
            }

    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']

        # test to see if user exists
        result = db.session.query(Players).filter(Players.username==username).first()
        if result != None:
            if result.hashed==None:
                session['id'] = result.player_id
                return redirect(url_for('set_password'))
            password = result.hashed
            if sha256_crypt.verify(password_candidate, password):
                #login successful
                session['logged_in'] = True
                session['first_name'] = result.first_name
                session['id'] = result.player_id
                session['access_level'] = ACCESS[result.type]
                session['team'] = result.team_id
                flash('You have successfully logged in', 'success')
                return redirect('/')
            else:
                error = 'Invalid Login'
                return render_template('login.html', error=error)
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/logout')
@login_required()
def logout():
    session.clear()
    return redirect('/')

@app.route('/')
def index():
    home_fixture_details = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==True).add_columns(Teams.team_name, FixtureDetails.fixture_id, FixtureDetails.goals).subquery()

    fixtures = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.played==False).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).order_by(Fixture.date).limit(3).all()

    results = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.played==True).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).order_by(Fixture.date.desc()).limit(3).all()


    return render_template('home.html', fixtures=fixtures, results=results)

# ADMIN SECTION
@app.route('/admin_page')
@login_required(2)
def admin_page():
    return render_template('admin_page.html')

@app.route('/add_team', methods=['GET', 'POST'])
@login_required(2)
def add_team():
    if request.method == 'POST':
        team_name = request.form['team_name']
        team = Teams(team_name)
        db.session.add(team)
        db.session.commit()
        # print(team_name)
    return render_template('add_team.html')

@app.route('/add_league', methods=['GET', 'POST'])
@login_required(2)
def add_league():
    if request.method == 'POST':
        league_name = request.form['league_name']
        league = Leagues(league_name)
        db.session.add(league)
        db.session.commit()
    return render_template('add_league.html')

@app.route('/add_fixture', methods=['GET', 'POST'])
@login_required(2)
def add_fixture():
    teams = db.session.query(Teams).all()
    leagues = db.session.query(Leagues).all()

    if request.method == 'POST':
        if request.form['home_team'] != request.form['away_team']:
            home_team = request.form['home_team'].split(' | ')[0]
            away_team = request.form['away_team'].split(' | ')[0]
            league = request.form['league'].split(' | ')[0]
            date = request.form['date']
            time = request.form['time']
            fixture = Fixture(league, date, time, False, None)
            db.session.add(fixture)
            db.session.commit()       
            fixture.fixture_id
            home = FixtureDetails(fixture.fixture_id, home_team, True, None, None, None)
            away = FixtureDetails(fixture.fixture_id, away_team, False, None, None, None)
            db.session.add(home)
            db.session.add(away)
            db.session.commit()

    return render_template('add_fixture.html', teams = teams, leagues = leagues)

@app.route('/add_player', methods=['GET', 'POST'])
@login_required(2)
def add_player():
    teams = db.session.query(Teams).all()
    if request.method =='POST':
        username = request.form['username']
        first_name=request.form['first_name']
        last_name = request.form['last_name']
        team_id=request.form['team'].split(' | ')[0]
        # print(team_id)/
        player=Players(team_id, first_name, last_name, username, None, None,None)
        db.session.add(player)
        db.session.commit()

    return render_template('add_player.html', teams=teams)

@app.route('/set_result/<string:id>', methods=['GET', 'POST'])
@login_required(2)
def set_result(id):

    home_fixture_details = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==True).add_columns(Teams.team_name, FixtureDetails.fixture_id, FixtureDetails.goals).subquery()

    fixture = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.fixture_id==id).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.team_id, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).first()
    
    if request.method=='POST':
        Fixture.query.filter(Fixture.fixture_id==id).update(dict(played=True))
        if request.form['home_score'] > request.form['away_score']:
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==True).update(dict(goals=request.form['home_score'], goals_against=request.form['away_score'], result='Win',points=3))
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==False).update(dict(goals=request.form['away_score'], goals_against=request.form['home_score'], result='Loss',points=0))
        elif request.form['home_score'] < request.form['away_score']:
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==True).update(dict(goals=request.form['home_score'], goals_against=request.form['away_score'], result='Loss',points=0))
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==False).update(dict(goals=request.form['away_score'], goals_against=request.form['home_score'],result='Win',points=3))
        else:
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==True).update(dict(goals=request.form['home_score'], goals_against=request.form['away_score'],result='Draw',points=1))
            FixtureDetails.query.filter(FixtureDetails.fixture_id==id, FixtureDetails.home==False).update(dict(goals=request.form['away_score'], goals_against=request.form['home_score'],result='Draw',points=1))
        
        db.session.commit()
        return redirect(url_for('add_goals', fixture=id, **request.args))
        
    return render_template('set_result.html', fixture=fixture)

@app.route('/add_goals', methods=['GET', 'POST'])
@login_required(2)
def add_goals():
    home_fixture_details = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==True).add_columns(Teams.team_name, FixtureDetails.fixture_id, FixtureDetails.goals).subquery()

    fixture = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.fixture_id==request.args['fixture']).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.team_id, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).first()

    home_players = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).join(FixtureDetails, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.fixture_id==request.args['fixture'], FixtureDetails.home==True).add_columns(Players.team_id, Players.first_name, Players.last_name, Players.player_id, Teams.team_name, Players.position)

    away_players = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).join(FixtureDetails, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.fixture_id==request.args['fixture'], FixtureDetails.home==False).add_columns(Players.team_id, Players.first_name, Players.last_name, Players.player_id, Teams.team_name, Players.position)

    home_goals = fixture[4]
    away_goals = fixture[6]

    points = {'Goalkeeper':{'Goal':6, 'Assist': 3, 'clean_sheet': 4, 'appearance': 2}, 
              'Defender':{'Goal':6, 'Assist': 3, 'clean_sheet': 4, 'appearance': 2}, 
              'Midfielder':{'Goal':5, 'Assist': 3, 'clean_sheet': 1, 'appearance': 2},
              'Forward':{'Goal':4, 'Assist': 3, 'clean_sheet': 0, 'appearance': 2}}

    if request.method == 'POST':
        stats = list(request.form.items())
        for stat in stats:
            print(stat)
            if len(stat[1]) > 2:
                # print(stat[1].split(' | '))
                type = stat[0][:-2]
                player= stat[1].split(' | ')[1]
                # print(points[stat[1].split(' | ')[3]][type])
                stat = Stats(player, request.args['fixture'], type, points[stat[1].split(' | ')[3]][type])
                db.session.add(stat)
        
        # db.session.commit()
        home = db.session.query(FixtureDetails).filter(FixtureDetails.fixture_id==request.args['fixture'], FixtureDetails.home==True).add_columns(FixtureDetails.team_id).first()
        away = db.session.query(FixtureDetails).filter(FixtureDetails.fixture_id==request.args['fixture'], FixtureDetails.home==False).add_columns(FixtureDetails.team_id).first()
        # print(home.team_id)
        home_team = db.session.query(Stats).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==request.args['fixture'], Stats.stat_type=='appearance', Players.team_id==home.team_id).add_columns(Players.first_name, Stats.player_id, Players.position).all()
        away_team = db.session.query(Stats).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==request.args['fixture'], Stats.stat_type=='appearance', Players.team_id==away.team_id).add_columns(Players.first_name, Stats.player_id, Players.position).all()

        if request.form['home_clean_sheet'] == 'Y':
            for player in home_team:
                stat = Stats(player.player_id, request.args['fixture'], 'clean_sheet', points[player.position]['clean_sheet'])
                db.session.add(stat)

        if request.form['away_clean_sheet'] == 'Y':
            for player in away_team:
                stat = Stats(player.player_id, request.args['fixture'], 'clean_sheet', points[player.position]['clean_sheet'])
                db.session.add(stat)

        db.session.commit()

    return render_template('add_goals.html', fixture=fixture, home_goals=home_goals, away_goals=away_goals, home_players=home_players, away_players=away_players)

# Player section
@app.route('/set_password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'POST':
        if request.form['password']==request.form['confirm_password']:
            Players.query.filter(Players.player_id==session['id']).update(dict(hashed=sha256_crypt.hash(str(request.form['password']))))
            db.session.commit()
            flash('Password Updated')
            return redirect('/login')

    return render_template('change_password.html')

@app.route('/account')
@login_required(1)
def my_account():
    return render_template('my_account.html')

@app.route('/edit_player', methods=['GET', 'POST'])
@login_required(1)
def edit_player():
    player = db.session.query(Players).filter(Players.player_id==1).first()

    if request.method == 'POST':
        Players.query.filter(Players.player_id==1).update(dict(first_name=request.form['first_name'], last_name=request.form['last_name'], position=request.form['position'], squad_number=request.form['squad_number']))
        db.session.commit()
        flash('Details Updated')
        return redirect('/account')

    return render_template('edit_player.html', player=player)

# Public section
@app.route('/fixtures')
def fixtures():
    home_fixture_details = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==True).add_columns(Teams.team_name, FixtureDetails.fixture_id, FixtureDetails.goals).subquery()

    fixtures = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.played==False).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).order_by(Fixture.date).all()

    results = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.played==True).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).order_by(Fixture.date).all()
    return render_template('fixtures.html', fixtures=fixtures, results=results)

@app.route('/result/<string:id>', methods=['GET', 'POST'])
def view_result(id):
    home_fixture_details = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==True).add_columns(Teams.team_name, FixtureDetails.fixture_id, FixtureDetails.goals).subquery()

    result = db.session.query(FixtureDetails).join(Teams, FixtureDetails.team_id==Teams.team_id).filter(FixtureDetails.home==False).join(Fixture, FixtureDetails.fixture_id==Fixture.fixture_id).filter(Fixture.fixture_id==id).join(home_fixture_details, FixtureDetails.fixture_id==home_fixture_details.c.fixture_id).add_columns(FixtureDetails.fixture_id, home_fixture_details.c.team_name, home_fixture_details.c.team_id, home_fixture_details.c.goals, Teams.team_name, FixtureDetails.goals, Fixture.time, Fixture.date, Fixture.played).first()

    game_stats = {}
    home_team = db.session.query(FixtureDetails).filter(FixtureDetails.fixture_id==id, FixtureDetails.home==True).add_columns(FixtureDetails.team_id).first()
    away_team = db.session.query(FixtureDetails).filter(FixtureDetails.fixture_id==id, FixtureDetails.home==False).add_columns(FixtureDetails.team_id).first()

    game_stats['home_goals'] = db.session.query(Stats.player_id, func.count(Stats.stat_type)).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==id ,Players.team_id==home_team.team_id, Stats.stat_type=='Goal').add_columns(Stats.stat_type, Players.last_name).group_by(Stats.stat_type, Players.last_name, Stats.stat_type, Stats.player_id).all()
    game_stats['home_assist'] = db.session.query(Stats.player_id, func.count(Stats.stat_type)).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==id ,Players.team_id==home_team.team_id, Stats.stat_type=='Assist').add_columns(Stats.stat_type, Players.last_name).group_by(Stats.stat_type, Players.last_name, Stats.stat_type, Stats.player_id).all()
    game_stats['home_lineup'] = db.session.query(Stats).join(Players, Stats.player_id==Players.player_id).join(FixtureDetails, Stats.fixture_id==FixtureDetails.fixture_id).filter(FixtureDetails.fixture_id==id, Players.team_id==home_team.team_id, Stats.stat_type=='appearance').add_columns(Players.squad_number,Players.first_name ,Players.last_name, Stats.stat_type, Stats.player_id).order_by(Players.squad_number).all()

    game_stats['away_goals'] = db.session.query(Stats.player_id, func.count(Stats.stat_type)).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==id ,Players.team_id==away_team.team_id, Stats.stat_type=='Goal').add_columns(Stats.stat_type, Players.last_name).group_by(Stats.stat_type, Players.last_name, Stats.stat_type, Stats.player_id).all()
    game_stats['away_assist'] = db.session.query(Stats.player_id, func.count(Stats.stat_type)).join(Players, Stats.player_id==Players.player_id).filter(Stats.fixture_id==id ,Players.team_id==away_team.team_id, Stats.stat_type=='Assist').add_columns(Stats.stat_type, Players.last_name).group_by(Stats.stat_type, Players.last_name, Stats.stat_type, Stats.player_id).all()
    game_stats['away_lineup'] = db.session.query(Stats).join(Players, Stats.player_id==Players.player_id).join(FixtureDetails, Stats.fixture_id==FixtureDetails.fixture_id).filter(FixtureDetails.fixture_id==id, Players.team_id==away_team.team_id, Stats.stat_type=='appearance').add_columns(Players.squad_number,Players.first_name ,Players.last_name, Stats.stat_type, Stats.player_id).order_by(Players.squad_number).all()

    return render_template('result.html', result=result, game_stats=game_stats)

@app.route('/players')
def players():
    players = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).add_columns(Players.first_name, Players.last_name, Players.squad_number, Teams.team_name, Players.player_id).all()
    players = {}
    
    players['defenders'] = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).filter(Players.position=='Defender', Teams.team_id==1).add_columns(Players.first_name, Players.last_name, Players.squad_number, Teams.team_name, Players.player_id, Players.position).order_by(Players.squad_number).all()
    players['midfielders'] = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).filter(Players.position=='Midfielder', Teams.team_id==1).add_columns(Players.first_name, Players.last_name, Players.squad_number, Teams.team_name, Players.player_id, Players.position).order_by(Players.squad_number).all()
    players['forwards'] = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).filter(Players.position=='Forward', Teams.team_id==1).add_columns(Players.first_name, Players.last_name, Players.squad_number, Teams.team_name, Players.player_id, Players.position).order_by(Players.squad_number).all()
    players['goalkeepers'] = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).filter(Players.position=='Goalkeeper', Teams.team_id==1).add_columns(Players.first_name, Players.last_name, Players.squad_number, Teams.team_name, Players.player_id, Players.position).order_by(Players.squad_number).all()

    return render_template('players.html', players=players)

@app.route('/player/<string:id>')
def player(id):
    player = db.session.query(Players).filter(Players.player_id==id).subquery()
    appearance = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('appearances')).filter(Stats.player_id==id,Stats.stat_type=='appearance').group_by(Stats.player_id).subquery()
    goals = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('goals')).filter(Stats.player_id==id, Stats.stat_type=='Goal').group_by(Stats.player_id).subquery()
    assists = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('assists')).filter(Stats.player_id==id, Stats.stat_type=='Assist').group_by(Stats.player_id).subquery() 
    cs = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('clean_sheets')).filter(Stats.player_id==id, Stats.stat_type=='clean_sheet').group_by(Stats.player_id).subquery() 
    first_appearance = db.session.query(Stats).join(Fixture, Stats.fixture_id==Fixture.fixture_id).filter(Stats.player_id==id,Stats.stat_type=='appearance', Stats.player_id==id).add_columns(Fixture.date).order_by(Fixture.date).subquery()
    stats = db.session.query(player).join(appearance, player.c.player_id==appearance.c.player_id).outerjoin(goals,player.c.player_id==goals.c.player_id).outerjoin(assists, player.c.player_id==assists.c.player_id).outerjoin(cs, player.c.player_id==cs.c.player_id).join(first_appearance, player.c.player_id==first_appearance.c.player_id).add_columns(player.c.first_name, appearance.c.appearances, goals.c.goals, assists.c.assists, cs.c.clean_sheets, first_appearance.c.date).first()
    # print(stats)
    # player['goals'] = db.session.query(func.count(Stats.stat_type)).filter(Stats.player_id==id, Stats.stat_type=='Goal').group_by(Stats.stat_type).count()

    # player['appearances'] = db.session.query(Stats.stat_type).filter(Stats.player_id==id, Stats.stat_type=='appearance').count()
    # print(player)
    # first_app = db.session.query(Stats).join(Fixture, Stats.fixture_id==Fixture.fixture_id).filter(Stats.player_id==id).add_columns(Fixture.date).order_by(Fixture.date).first()
    
    # if first_app == None:
    #     player['first_appearance'] = 'N/A'
    # else:
    #     player['first_appearance'] = first_app[1].strftime('%dth %B %Y')

    # player['goals'] = db.session.query(Stats.stat_type).filter(Stats.player_id==id, Stats.stat_type=='Goal').count()
    # player['assists'] = db.session.query(Stats.stat_type).filter(Stats.player_id==id, Stats.stat_type=='Assist').count()
    # player['details'] = db.session.query(Players).join(Teams, Players.team_id==Teams.team_id).filter(Players.player_id==id).add_columns(Players.squad_number, Players.first_name, Players.last_name, Teams.team_name, Teams.team_id).first()

    if stats.date == None:
        stats = (11, 1, 'Johnny', 'Boutwood', None, None, 3, 'Defender', 'Player', 'Johnny', 2, None, None, 1, (2021, 11, 4))
    return render_template('player.html', stats=stats)

@app.route('/league_table')
def league_table():

    info = db.session.query(FixtureDetails.team_id, func.count(FixtureDetails.result), func.sum(FixtureDetails.points), func.sum(FixtureDetails.goals), func.sum(FixtureDetails.goals_against)).join(Teams,FixtureDetails.team_id==Teams.team_id).group_by(FixtureDetails.team_id, Teams.team_name).add_columns(Teams.team_name).order_by(func.sum(FixtureDetails.points).desc(), func.sum(FixtureDetails.goals).desc()).all()

    positions = [i+1 for i in range(len(info))]
    table = zip(positions, info)

    return render_template('league_table.html', table=table)

@app.route('/team_data/<string:id>')
def team_data(id):
    players = db.session.query(Players).filter(Players.team_id==id).subquery()
    appearance = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('appearances')).filter(Stats.stat_type=='appearance').group_by(Stats.player_id).subquery()
    goals = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('goals')).filter(Stats.stat_type=='Goal').group_by(Stats.player_id).subquery()
    assists = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('assists')).filter(Stats.stat_type=='Assist').group_by(Stats.player_id).subquery() 
    cs = db.session.query(Stats.player_id, func.count(Stats.stat_type).label('clean_sheets')).filter(Stats.stat_type=='clean_sheet').group_by(Stats.player_id).subquery() 
    fp = db.session.query(Stats.player_id, func.sum(Stats.fp_points).label('fp_points')).group_by(Stats.player_id).subquery() 
    stats = db.session.query(players).join(appearance, players.c.player_id==appearance.c.player_id).outerjoin(goals,players.c.player_id==goals.c.player_id).outerjoin(assists, players.c.player_id==assists.c.player_id).outerjoin(cs, players.c.player_id==cs.c.player_id).outerjoin(fp, players.c.player_id==fp.c.player_id).add_columns(appearance.c.appearances, goals.c.goals, assists.c.assists, cs.c.clean_sheets, fp.c.fp_points).order_by(fp.c.fp_points.desc()).all()

    return render_template('teams.html', stats=stats)

if __name__ == '__main__':
    
    app.run()