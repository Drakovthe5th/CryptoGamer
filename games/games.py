import os
import request
from flask import Blueprint, render_template, send_from_directory
from .clicker_game import ClickerGame
from .spin_game import SpinGame
from .trivia_quiz import TriviaQuiz
from .trex_runner import TRexRunner
from .edge_surf import EdgeSurf
from datetime import time

games_bp = Blueprint('games', __name__, url_prefix='/games')

GAME_REGISTRY = {
    "clicker": ClickerGame(),
    "spin": SpinGame(),
    "trivia": TriviaQuiz(),
    "trex": TRexRunner(),
    "edge_surf": EdgeSurf()
}

@games_bp.route('/<game_name>')
def game_hub(game_name):
    game = GAME_REGISTRY.get(game_name.lower())
    if not game:
        return "Game not found", 404
    return render_template(f"games/{game_name}.html", 
                           game_name=game_name,
                           game_data=game.get_init_data())

@games_bp.route('/<game_name>/static/<path:filename>')
def game_static(game_name, filename):
    return send_from_directory(f"games/static/{game_name}", filename)

# Game management endpoints
@games_bp.route('/<game_name>/start', methods=['POST'])
def start_game(game_name):
    return GAME_REGISTRY[game_name].start_game()

@games_bp.route('/<game_name>/action', methods=['POST'])
def game_action(game_name):
    return GAME_REGISTRY[game_name].handle_action(request.json)

@games_bp.route('/<game_name>/end', methods=['POST'])
def end_game(game_name):
    return GAME_REGISTRY[game_name].end_game()