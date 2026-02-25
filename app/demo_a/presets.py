"""プリセットスキーマ定義（デモA用）"""

PRESETS: dict[str, dict] = {
    "引合概要": {
        "name": "引合概要",
        "description": "テンダー書類から案件概要を抽出（Instructions to Bidders, Project Overview向け）",
        "fields": [
            {"name": "project_name", "type": "テキスト", "description": "プロジェクト名・案件名"},
            {"name": "customer", "type": "テキスト", "description": "顧客名（発注者）"},
            {"name": "contact_name", "type": "テキスト", "description": "顧客側担当者名"},
            {"name": "contact_email", "type": "テキスト", "description": "顧客側担当者メールアドレス"},
            {"name": "contract_term", "type": "テキスト", "description": "契約期間（本契約＋延長オプション）"},
            {"name": "currency", "type": "テキスト", "description": "取引通貨"},
            {"name": "bid_deadline", "type": "テキスト", "description": "入札締切日"},
            {"name": "submission_platform", "type": "テキスト", "description": "提出先プラットフォーム"},
            {"name": "project_location", "type": "テキスト", "description": "プロジェクト所在地・支援拠点"},
            {"name": "water_depth", "type": "テキスト", "description": "水深"},
        ],
    },
    "品目リスト": {
        "name": "品目リスト",
        "description": "CallOff/Technical Offer/入票明細から品目情報を抽出",
        "fields": [
            {"name": "item_no", "type": "テキスト", "description": "品目番号"},
            {
                "name": "usage",
                "type": "テキスト",
                "description": "用途（Casing / Tubing / Pup Joint / Coupling / Accessory）",
            },
            {"name": "grade", "type": "テキスト", "description": "鋼種・グレード名"},
            {"name": "od", "type": "テキスト", "description": "外径（Outside Diameter）"},
            {"name": "wt", "type": "テキスト", "description": "肉厚・単重（Wall Thickness / Weight per foot）"},
            {"name": "connection", "type": "テキスト", "description": "ネジ種・継手タイプ"},
            {"name": "drift", "type": "テキスト", "description": "ドリフト径（Drift Diameter）"},
            {"name": "length", "type": "テキスト", "description": "長さ・レンジ"},
            {"name": "quantity", "type": "テキスト", "description": "数量（本数またはメートル）"},
            {"name": "unit_price", "type": "数値", "description": "単価（USD）"},
            {"name": "delivery_date", "type": "テキスト", "description": "納期"},
        ],
    },
    "契約条件": {
        "name": "契約条件",
        "description": "Exhibit D / Base Contractから契約条件を抽出",
        "fields": [
            {
                "name": "price_firmness",
                "type": "テキスト",
                "description": "価格確定条件（固定 or 変動、サーチャージ可否）",
            },
            {"name": "incoterms", "type": "テキスト", "description": "受渡条件（INCOTERMS）の選択肢"},
            {"name": "cancellation_fees", "type": "テキスト", "description": "WIPキャンセル費用（製造段階別）"},
            {"name": "quantity_tolerance", "type": "テキスト", "description": "注文数量の許容差（プラス/マイナス）"},
            {
                "name": "personnel_terms",
                "type": "テキスト",
                "description": "人件費条件（オフショア人員の開始/終了タイミング、含む費目）",
            },
            {
                "name": "inventory_management",
                "type": "テキスト",
                "description": "VMI在庫管理条件（最低/最大在庫、所有権、FIFO等）",
            },
            {"name": "logistics_terms", "type": "テキスト", "description": "輸送条件（積込/荷下ろし負担、梱包責任）"},
            {
                "name": "credit_policy",
                "type": "テキスト",
                "description": "返品・クレジットポリシー（Prime品/修理可能品/修理不可品）",
            },
            {"name": "third_party_markup", "type": "テキスト", "description": "第三者サービスのマークアップ条件"},
            {"name": "late_delivery_penalty", "type": "テキスト", "description": "納期遅延ペナルティの有無・条件"},
        ],
    },
}


def list_presets() -> list[dict]:
    """全プリセットのリストを返す。"""
    return list(PRESETS.values())


def get_preset(name: str) -> dict:
    """プリセット名でプリセットを取得する。存在しない場合はKeyError。"""
    if name not in PRESETS:
        raise KeyError(f"プリセット '{name}' が見つかりません")
    return PRESETS[name]
