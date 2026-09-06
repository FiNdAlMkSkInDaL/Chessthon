"""Original attack-coordination features, white minus black, for offline R&D.

Attack masks are geometric (including pinned pieces). Checking destinations
are opportunities, not a claim that every such move is legal or safe by SEE.
No engine code, answers or published evaluation coefficients are embedded.
"""
import chess
import numpy as np

NAMES = ['weak_ring', 'double_ring', 'queen_contact', 'knight_checks',
         'bishop_checks', 'rook_checks', 'queen_checks', 'coordinated_ring',
         'pressure_squared', 'restricted_flights', 'pawn_storm',
         'pawn_levers', 'open_king_files', 'queen_proximity']

def extract(b):
    rows=[]
    maps={}; doubles={}; pawnmaps={}; piece_maps={}
    for c in (True,False):
        union=double=pawns=0; parts=[]
        for s in chess.scan_forward(b.occupied_co[c]):
            p=b.piece_type_at(s); a=b.attacks_mask(s)
            double|=union&a; union|=a; parts.append((p,s,a))
            if p==chess.PAWN:pawns|=a
        maps[c]=union; doubles[c]=double; pawnmaps[c]=pawns;piece_maps[c]=parts
    for c in (True,False):
        vals=np.zeros(len(NAMES),dtype=np.int32)
        # Queenless attacks remain in the existing evaluator. This residual
        # specializes in coordinated queen attacks, not all king activity.
        if not b.pieces_mask(chess.QUEEN,c):rows.append(vals);continue
        k=b.king(not c); zone=chess.BB_KING_ATTACKS[k]; own=b.occupied_co[c]
        weak=maps[c]&(~maps[not c] | (doubles[c]&~doubles[not c]&~pawnmaps[not c]))
        vals[0]=(weak&zone).bit_count()
        vals[1]=(doubles[c]&zone&~pawnmaps[not c]).bit_count()
        # Occupancy-sensitive checking rays from the defending king.
        rays={2:chess.BB_KNIGHT_ATTACKS[k],
              3:chess.BB_DIAG_ATTACKS[k][chess.BB_DIAG_MASKS[k]&b.occupied],
              4:chess.BB_RANK_ATTACKS[k][chess.BB_RANK_MASKS[k]&b.occupied]|
                chess.BB_FILE_ATTACKS[k][chess.BB_FILE_MASKS[k]&b.occupied]}
        rays[5]=rays[3]|rays[4]
        attackers=pressure=0; checks=[0]*6
        safe=(~maps[not c] | (doubles[c]&~doubles[not c]&~pawnmaps[not c]))&~own
        for p,s,a in piece_maps[c]:
            if p not in (2,3,4,5):continue
            hits=(a&zone).bit_count()
            if hits:attackers+=1;pressure+=hits*(2 if p<4 else p)
            checks[p]|=a&rays[p]&safe
            if p==5:
                other=0
                for pt,ss,aa in piece_maps[c]:
                    if ss!=s:other|=aa
                vals[2]+=(a&zone&other&~own&~pawnmaps[not c]).bit_count()
                vals[13]+=max(0,5-chess.square_distance(s,k))
        for p in (2,3,4,5):vals[p+1]=checks[p].bit_count()
        vals[7]=pressure*max(0,min(4,attackers)-1)
        vals[8]=min(64,pressure)**2
        vals[9]=max(0,3-(zone&~b.occupied_co[not c]&~maps[c]).bit_count())*min(3,attackers)
        for s in b.pieces(chess.PAWN,c):
            d=chess.square_distance(s,k)
            if abs(chess.square_file(s)-chess.square_file(k))<=1:
                vals[10]+=max(0,4-d)
            vals[11]+=(chess.BB_PAWN_ATTACKS[c][s]&b.pieces_mask(chess.PAWN,not c)&(zone|chess.BB_SQUARES[k])).bit_count()
        kf=chess.square_file(k)
        vals[12]=sum(not (b.pieces_mask(chess.PAWN,not c)&chess.BB_FILES[f]) for f in range(max(0,kf-1),min(8,kf+2))) * min(3,attackers)
        rows.append(vals)
    return rows[0]-rows[1]

def phase(b):
    return min(24,sum(len(b.pieces(pt,c))*w for pt,w in [(2,1),(3,1),(4,2),(5,4)] for c in (True,False)))/24
