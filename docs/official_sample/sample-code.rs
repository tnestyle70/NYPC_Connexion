use std::{
    fmt::{self, Display, Formatter},
    io::{self, BufRead, Write, stdout},
    str::FromStr,
};

/// 게임 보드의 열 번호
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Column {
    A,
    B,
    C,
    D,
    E,
    F,
}

/// 게임 보드의 행 번호
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Row {
    _1,
    _2,
    _3,
    _4,
    _5,
    _6,
}

/// 게임 보드의 부호
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Sign {
    Minus,
    Plus,
}

/// 게임 타일의 색
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Color {
    R,
    G,
    B,
    Y,
}

/// 게임 타일의 문양
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Symbol {
    _1,
    _2,
    _3,
    _4,
}

/// 게임 보드의 칸
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct Cell {
    /// 게임 보드의 열
    col: Column,
    /// 게임 보드의 행
    row: Row,
    /// 게임 보드의 부호
    sign: Sign,
}

impl Cell {
    fn new(col: Column, row: Row, sign: Sign) -> Self {
        Cell { col, row, sign }
    }

    /// 해당 칸이 금지된 칸인 a1-, a4-, c3+, c6+, d1-, d4-, f3+, f6+ 중 하나가 아니라면 true를 반환
    fn is_valid(&self) -> bool {
        !matches!(
            self,
            Self {
                col: Column::A,
                row: Row::_1,
                sign: Sign::Minus
            } | Self {
                col: Column::A,
                row: Row::_4,
                sign: Sign::Minus
            } | Self {
                col: Column::C,
                row: Row::_3,
                sign: Sign::Plus
            } | Self {
                col: Column::C,
                row: Row::_6,
                sign: Sign::Plus
            } | Self {
                col: Column::D,
                row: Row::_1,
                sign: Sign::Minus
            } | Self {
                col: Column::D,
                row: Row::_4,
                sign: Sign::Minus
            } | Self {
                col: Column::F,
                row: Row::_3,
                sign: Sign::Plus
            } | Self {
                col: Column::F,
                row: Row::_6,
                sign: Sign::Plus
            }
        )
    }

    /// 주어진 두 칸이 인접한 칸인지 여부를 반환
    fn is_adjacent(&self, other: &Cell) -> bool {
        // 두 칸의 행, 열 번호 차이를 계산
        let dr = (other.row as i32) - (self.row as i32);
        let dc = (other.col as i32) - (self.col as i32);

        match (self.sign, other.sign) {
            (Sign::Minus, Sign::Plus) => {
                matches!((dr, dc), (0, 0) | (0, -1) | (-1, 0))
            }
            (Sign::Plus, Sign::Minus) => {
                matches!((dr, dc), (0, 0) | (0, 1) | (1, 0))
            }
            _ => false,
        }
    }

    /// 배치 가능한 모든 칸을 반환
    fn get_all_cells() -> Vec<Cell> {
        let mut cells = Vec::new();

        const COLUMNS: [Column; 6] = [
            Column::A,
            Column::B,
            Column::C,
            Column::D,
            Column::E,
            Column::F,
        ];
        const ROWS: [Row; 6] = [Row::_1, Row::_2, Row::_3, Row::_4, Row::_5, Row::_6];
        const SIGNS: [Sign; 2] = [Sign::Minus, Sign::Plus];

        for col in COLUMNS {
            for row in ROWS {
                for sign in SIGNS {
                    let cell = Cell::new(col, row, sign);
                    if cell.is_valid() {
                        cells.push(cell);
                    }
                }
            }
        }
        cells
    }
}

/// 타일을 나타내는 구조체
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct Tile {
    /// 타일의 색
    color: Color,
    /// 타일의 문양
    symbol: Symbol,
}

impl Tile {
    fn new(color: Color, symbol: Symbol) -> Self {
        Tile { color, symbol }
    }

    /// 점수 계산시 두 타일을 같은 타일로 볼 것인가를 반환
    ///
    /// 인자 목록
    /// - other: 비교할 타일
    /// - is_first: 선후공 (true: 선공 / 문양을 사용, false: 후공 / 색을 사용)
    fn is_same(&self, other: &Tile, is_first: bool) -> bool {
        if is_first {
            self.symbol == other.symbol
        } else {
            self.color == other.color
        }
    }
}

/// 게임 상태를 관리하는 구조체
struct Game {
    /// 내 타일 목록
    my_tiles: Vec<Tile>,
    /// 상대 타일 목록
    opp_tiles: Vec<Tile>,
    /// 선후공 (true: 선공, false: 후공)
    is_first: bool,
    /// 현재 보드에 배치된 칸과 타일 목록
    board: Vec<(Cell, Tile)>,
}

impl Game {
    fn new(my_tiles: Vec<Tile>, opp_tiles: Vec<Tile>, is_first: bool) -> Self {
        Game {
            my_tiles,
            opp_tiles,
            is_first,
            board: Vec::new(),
        }
    }
    // ================================ [필수 구현] ================================
    /// 현재 상태를 기반으로 놓아야 할 칸과 타일을 계산함
    ///
    /// 인자 목록
    /// - _my_time: 내 프로그램의 남은 시간
    /// - _opp_time: 상대 프로그램의 남은 시간
    fn calculate_move(&self, _my_time: i32, _opp_time: i32) -> (Cell, Tile) {
        let mut best_move: Option<(Cell, Tile)> = None;
        let mut best_score = 0;

        // 가능한 모든 행동중 최대 점수를 찾음
        for tile in &self.my_tiles {
            for cell in Cell::get_all_cells() {
                // 이미 배치된 칸인지 확인
                if !self.board.iter().any(|(c, _)| *c == cell) {
                    let mut test_board = self.board.clone();
                    test_board.push((cell, *tile));

                    // 점수를 계산 후 최고 점수를 갱신
                    let score = Self::calculate_score(&test_board, self.is_first);
                    if score > best_score {
                        best_score = score;
                        best_move = Some((cell, *tile));
                    }
                }
            }
        }

        best_move.expect("No valid move found")
    }
    // ============================== [필수 구현 끝] ==============================

    /// 자신 혹은 상대의 행동을 기반으로 상태를 업데이트 함
    ///
    /// 인자 목록
    /// - my_action: 자신의 행동 여부 (true: 자신, false: 상대)
    /// - action: 자신 혹은 상대가 배치한 칸과 타일
    /// - get: 자신 혹은 상대가 뽑은 타일. 없으면 None.
    /// - _used_time: 상대가 사용한 시간. 자신의 행동인 경우 None.
    fn update_action(
        &mut self,
        my_action: bool,
        action: (Cell, Tile),
        get: Option<Tile>,
        _used_time: Option<i32>,
    ) {
        // 전체 보드에 칸과 타일 추가
        self.board.push(action);

        if my_action {
            // 내 타일에서 사용한 타일 제거
            let tile_pos = self.my_tiles.iter().position(|t| *t == action.1).unwrap();
            self.my_tiles.remove(tile_pos);

            // 뽑아온 타일이 있으면 타일 목록에 타일 추가
            if let Some(tile) = get {
                self.my_tiles.push(tile);
            }
        } else {
            // 상대 타일에서 사용한 타일 제거
            let tile_pos = self.opp_tiles.iter().position(|t| *t == action.1).unwrap();
            self.opp_tiles.remove(tile_pos);

            // 뽑아온 타일이 있으면 타일 목록에 타일 추가
            if let Some(tile) = get {
                self.opp_tiles.push(tile);
            }
        }
    }

    /// 보드와 선후공를 기반으로 점수를 계산함
    ///
    /// 인자 목록
    /// - board: 보드
    /// - is_first: 선후공 (true: 선공 / 문양을 사용, false: 후공 / 색을 사용)
    fn calculate_score(board: &[(Cell, Tile)], is_first: bool) -> i32 {
        if board.is_empty() {
            return 0;
        }

        let n = board.len();
        let mut adj = vec![vec![false; n]; n];

        // 선후공을 고려하여 타일들의 인접행렬을 계산함
        for i in 0..n {
            for j in 0..n {
                if i == j
                    || (board[i].0.is_adjacent(&board[j].0)
                        && board[i].1.is_same(&board[j].1, is_first))
                {
                    adj[i][j] = true;
                }
            }
        }

        // Warshall algorithm을 사용하여 연결 성분을 계산
        for k in 0..n {
            for i in 0..n {
                for j in 0..n {
                    if adj[i][k] && adj[k][j] {
                        adj[i][j] = true;
                    }
                }
            }
        }

        // 각 타일의 점수는 같은 연결 성분에 속한 타일의 수, 총점은 모든 타일의 점수 총합
        adj.iter()
            .map(|row| row.iter().filter(|&&x| x).count() as i32)
            .sum()
    }
}

// ================================ 입출력 및 파싱을 위한 Helper 시작 ================================

impl Column {
    fn from_char(c: char) -> Option<Self> {
        match c {
            'a' => Some(Column::A),
            'b' => Some(Column::B),
            'c' => Some(Column::C),
            'd' => Some(Column::D),
            'e' => Some(Column::E),
            'f' => Some(Column::F),
            _ => None,
        }
    }
}

impl Display for Column {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let c = match self {
            Column::A => 'a',
            Column::B => 'b',
            Column::C => 'c',
            Column::D => 'd',
            Column::E => 'e',
            Column::F => 'f',
        };
        write!(f, "{c}")
    }
}

impl Row {
    fn from_char(c: char) -> Option<Self> {
        match c {
            '1' => Some(Row::_1),
            '2' => Some(Row::_2),
            '3' => Some(Row::_3),
            '4' => Some(Row::_4),
            '5' => Some(Row::_5),
            '6' => Some(Row::_6),
            _ => None,
        }
    }
}

impl Display for Row {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let c = match self {
            Row::_1 => '1',
            Row::_2 => '2',
            Row::_3 => '3',
            Row::_4 => '4',
            Row::_5 => '5',
            Row::_6 => '6',
        };
        write!(f, "{c}")
    }
}

impl Sign {
    fn from_char(c: char) -> Option<Self> {
        match c {
            '-' => Some(Sign::Minus),
            '+' => Some(Sign::Plus),
            _ => None,
        }
    }
}

impl Display for Sign {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let c = match self {
            Sign::Minus => '-',
            Sign::Plus => '+',
        };
        write!(f, "{c}")
    }
}

impl Color {
    fn from_char(c: char) -> Option<Self> {
        match c {
            'R' => Some(Color::R),
            'G' => Some(Color::G),
            'B' => Some(Color::B),
            'Y' => Some(Color::Y),
            _ => None,
        }
    }
}

impl Display for Color {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let c = match self {
            Color::R => 'R',
            Color::G => 'G',
            Color::B => 'B',
            Color::Y => 'Y',
        };
        write!(f, "{c}")
    }
}

impl Symbol {
    fn from_char(c: char) -> Option<Self> {
        match c {
            '1' => Some(Symbol::_1),
            '2' => Some(Symbol::_2),
            '3' => Some(Symbol::_3),
            '4' => Some(Symbol::_4),
            _ => None,
        }
    }
}

impl Display for Symbol {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let c = match self {
            Symbol::_1 => '1',
            Symbol::_2 => '2',
            Symbol::_3 => '3',
            Symbol::_4 => '4',
        };
        write!(f, "{c}")
    }
}

impl FromStr for Cell {
    type Err = ();
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        if s.len() != 3 {
            return Err(());
        }
        let mut it = s.chars();
        let col = Column::from_char(it.next().unwrap()).ok_or(())?;
        let row = Row::from_char(it.next().unwrap()).ok_or(())?;
        let sign = Sign::from_char(it.next().unwrap()).ok_or(())?;
        let cell = Cell::new(col, row, sign);
        if cell.is_valid() { Ok(cell) } else { Err(()) }
    }
}

impl Display for Cell {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{}{}{}", self.col, self.row, self.sign)
    }
}

impl FromStr for Tile {
    type Err = ();
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        if s.len() != 2 {
            return Err(());
        }
        let mut it = s.chars();
        let color = Color::from_char(it.next().unwrap()).ok_or(())?;
        let symbol = Symbol::from_char(it.next().unwrap()).ok_or(())?;
        let tile = Tile::new(color, symbol);
        Ok(tile)
    }
}

impl Display for Tile {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{}{}", self.color, self.symbol)
    }
}

// ================================ 입출력 및 파싱을 위한 Helper 끝 ================================

/// 표준 입력을 통해 명령어를 처리하는 메인 함수
fn main() {
    let stdin = io::stdin();
    let mut game: Option<Game> = None;
    let mut is_first: Option<bool> = None;
    let mut last_move: Option<(Cell, Tile)> = None;

    for line in stdin.lock().lines() {
        let line = line.unwrap();
        if line.trim().is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split_whitespace().collect();
        let command = parts[0];

        match command {
            "READY" => {
                // 게임 시작
                is_first = Some(parts[1] == "FIRST");
                println!("OK");
                stdout().flush().unwrap();
            }
            "INIT" => {
                // 준비 단계 시작
                let my_tiles: Vec<Tile> = parts[1..6].iter().map(|&s| s.parse().unwrap()).collect();
                let opp_tiles: Vec<Tile> =
                    parts[6..11].iter().map(|&s| s.parse().unwrap()).collect();

                game = Some(Game::new(my_tiles, opp_tiles, is_first.unwrap()));
            }
            "TIME" => {
                // 배치 단계 시작
                let my_time: i32 = parts[1].parse().unwrap();
                let opp_time: i32 = parts[2].parse().unwrap();

                last_move = Some(game.as_ref().unwrap().calculate_move(my_time, opp_time));
                let (cell, tile) = last_move.as_ref().unwrap();
                println!("PUT {cell} {tile}");
                stdout().flush().unwrap();
            }
            "GET" => {
                // 배치 단계가 끝날때 뽑아온 타일을 이용해서 상태를 업데이트 함
                let get_tile = if parts[1] == "X0" {
                    None
                } else {
                    Some(parts[1].parse().unwrap())
                };

                game.as_mut()
                    .unwrap()
                    .update_action(true, last_move.unwrap(), get_tile, None);
            }
            "OPP" => {
                // 상대의 행동을 기반으로 상태를 업데이트 함
                let cell = parts[1].parse().unwrap();
                let tile = parts[2].parse().unwrap();
                let get_tile = if parts[3] == "X0" {
                    None
                } else {
                    Some(parts[3].parse().unwrap())
                };
                let opp_time: i32 = parts[4].parse().unwrap();

                game.as_mut()
                    .unwrap()
                    .update_action(false, (cell, tile), get_tile, Some(opp_time));
            }
            "FINISH" => {
                // 게임 종료
                break;
            }
            _ => {
                // 알 수 없는 명령어 처리
                eprintln!("Invalid command: {command}");
                std::process::exit(1);
            }
        }
    }
}
