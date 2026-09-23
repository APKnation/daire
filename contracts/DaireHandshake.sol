// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title  DaireHandshake
 * @notice STEP 1 CONTRACT — pipeline verification only.
 *
 *         Contract hii HAIHESABU credit score. Kazi yake moja tu: kuthibitisha
 *         kwamba mnyororo mzima wa zana unafanya kazi kabla hatujaandika logic
 *         halisi:
 *
 *              VS Code  ->  remixd  ->  Remix IDE  ->  MetaMask
 *                       ->  Sepolia testnet  ->  Sepolia Etherscan
 *
 *         Ukiweza ku-deploy hii, ku-call ping(), na kuona transaction yako
 *         kwenye Etherscan — mnyororo uko sawa, na tunaendelea Step 2
 *         (DaireCreditScore.sol) kwa uhakika.
 *
 * @dev    Kila kipengele hapa chini kimewekwa kwa makusudi ili ujaribu kitu
 *         tofauti kwenye Remix:
 *
 *           - constant     -> inasomwa bila gas, imeandikwa kwenye bytecode
 *           - immutable    -> inawekwa mara moja kwenye constructor, ni nafuu
 *           - storage      -> pingCount inabadilika, inagharimu gas
 *           - event        -> inaonekana kwenye tab ya "Logs" ya Etherscan
 *           - view function-> Remix inaionyesha kwa buluu (bure, hakuna tx)
 *           - write funct. -> Remix inaionyesha kwa machungwa (inahitaji MetaMask)
 */
contract DaireHandshake {
    // ---------------------------------------------------------------------
    // CONSTANTS
    // Hizi hazibadiliki kamwe. Hazichukui nafasi ya storage — zimeandikwa
    // moja kwa moja ndani ya bytecode, hivyo kuzisoma ni bure kabisa.
    // ---------------------------------------------------------------------

    string public constant SYSTEM = "DAIRE - Decentralized AI Reputation Engine";
    string public constant STAGE = "Step 1 - handshake / pipeline verification";
    string public constant DOC_REF = "DAIRE/SDD/001";

    // ---------------------------------------------------------------------
    // IMMUTABLES
    // Zinawekwa MARA MOJA tu, ndani ya constructor, kisha haziwezi kubadilika.
    // Ni nafuu kuliko storage ya kawaida kwa sababu nazo huingia kwenye bytecode.
    // ---------------------------------------------------------------------

    /// @notice Anwani iliyo-deploy contract hii. Ndiye "owner" wa awali.
    address public immutable deployer;

    /// @notice Muda (unix timestamp) contract ilipowekwa kwenye chain.
    uint256 public immutable deployedAt;

    // ---------------------------------------------------------------------
    // STORAGE
    // Hii ndiyo inayobadilika. Kila mabadiliko yanagharimu gas na yanaandikwa
    // kwenye ledger milele.
    // ---------------------------------------------------------------------

    /// @notice Idadi ya mara ping() imeitwa. Huu ndio ushahidi kwamba
    ///         transaction yako imefanikiwa kubadilisha hali ya blockchain.
    uint256 public pingCount;

    /// @notice Ujumbe wa mwisho uliotumwa kupitia ping().
    string public lastNote;

    // ---------------------------------------------------------------------
    // EVENTS
    // Events ni njia ya bei nafuu ya kuandika taarifa kwenye chain.
    // HAZIWEZI kusomwa na contract nyingine, LAKINI zinaonekana kwenye
    // Etherscan chini ya tab ya "Logs", na frontend/backend zinaweza
    // kuzisikiliza. Hapa ndipo DAIRE itakapotoa taarifa ya score baadaye.
    //
    // `indexed` inamaanisha unaweza kuchuja (filter) kwa thamani hiyo.
    // Unaruhusiwa `indexed` tatu tu kwa kila event.
    // ---------------------------------------------------------------------

    event Deployed(address indexed deployer, uint256 timestamp, string stage);
    event Ping(address indexed caller, uint256 indexed newCount, string note);

    // ---------------------------------------------------------------------
    // CONSTRUCTOR
    // Inakimbia MARA MOJA tu — wakati wa deployment. Baada ya hapo haipo tena.
    // ---------------------------------------------------------------------

    constructor() {
        deployer = msg.sender;      // msg.sender = anwani iliyotuma transaction
        deployedAt = block.timestamp; // saa ya block, si saa ya computer yako
        emit Deployed(msg.sender, block.timestamp, STAGE);
    }

    // ---------------------------------------------------------------------
    // WRITE FUNCTION  (inagharimu gas — MetaMask itaomba saini)
    // ---------------------------------------------------------------------

    /**
     * @notice Ongeza counter kwa moja na hifadhi ujumbe.
     * @dev    Hii ndiyo function utakayoitumia kuthibitisha kwamba unaweza
     *         kubadilisha hali ya blockchain. Baada ya kuiita, nenda Etherscan
     *         uone transaction yako.
     * @param  note Ujumbe wowote, mfano "handshake test 1".
     * @return Thamani mpya ya pingCount.
     */
    function ping(string calldata note) external returns (uint256) {
        pingCount += 1;
        lastNote = note;
        emit Ping(msg.sender, pingCount, note);
        return pingCount;
    }

    // ---------------------------------------------------------------------
    // READ FUNCTIONS  (bure kabisa — hakuna transaction, hakuna gas)
    // ---------------------------------------------------------------------

    /**
     * @notice Rudisha taarifa zote za contract kwa wito mmoja.
     * @dev    `view` inamaanisha function hii inasoma tu, haibadilishi kitu.
     *         Remix itaionyesha kwa rangi ya buluu.
     */
    function info()
        external
        view
        returns (
            string memory system,
            string memory stage,
            address who,
            uint256 when,
            uint256 pings,
            string memory note
        )
    {
        return (SYSTEM, STAGE, deployer, deployedAt, pingCount, lastNote);
    }

    /**
     * @notice Umri wa contract kwa sekunde tangu ilipo-deploy.
     * @dev    Mfano wa hesabu ndogo inayofanyika ON-CHAIN. Step 2 itafanya
     *         hesabu kubwa zaidi ya namna hii ili kupata credit score.
     */
    function ageInSeconds() external view returns (uint256) {
        return block.timestamp - deployedAt;
    }
}
