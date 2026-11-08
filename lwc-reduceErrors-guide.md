# 質問：LWCの`reduceErrors`は、常に使うのが最適ですか？

## 回答

いいえ、**常に使う必要はありません。** `reduceErrors`は、Salesforceから返ってきたエラーを、画面に表示しやすい**メッセージの配列**に変えるための補助関数です。エラー処理そのものを全部任せる関数ではありません。

たとえば、Apexのエラーでは`error.body.message`に文言が入ることがあります。一方、`getRecord`などのUI APIでは`error.body`が配列になるなど、返り方が異なります。複数の返り方をまとめて扱いたいときに`reduceErrors`が役立ちます。

**公式資料の該当箇所：** [Salesforce Developers「Handle Errors in Lightning Data Service」](https://developer.salesforce.com/docs/platform/lwc/guide/data-error.html)の「The body of the error response depends on the API that returns it」（APIごとの`body`の形）と、同ページの`ldsUtils`への案内。**「常に使う必要はない」という結論そのものを定めた公式リファレンスはありません。** 関数の用途からの判断です。

### Q. どんなときに使うと便利ですか？

次のように、エラーから表示用の文言を取り出したいときです。

- Apex、UI API、JavaScriptなど、**形の異なるエラーから表示文言を取り出したい**。
- **複数のエラーメッセージをまとめて表示したい**。
- 同じメッセージ取り出し処理を、複数のコンポーネントで使いたい。

```js
// LWC Recipes の ldsUtils.js をプロジェクトに配置した場合
import { reduceErrors } from 'c/ldsUtils';

const messages = reduceErrors(error); // 文字列の配列
this.errorMessage = messages.join('、') || '処理に失敗しました。';
```

`reduceErrors`はSalesforceの組み込み関数ではなく、[LWC Recipesのサンプル実装](https://github.com/trailheadapps/lwc-recipes/blob/main/force-app/main/default/lwc/ldsUtils/ldsUtils.js)です。上の例は、そのファイルを自分のプロジェクトに置いた場合の書き方です。

**公式資料の該当箇所：** [Salesforce Developers Blog「Displaying and logging errors」](https://developer.salesforce.com/blogs/2020/08/error-handling-best-practices-for-lightning-web-components)に、異なる形のエラーから文言を取り出すための`reduceErrors`の説明があります。返り値が文字列の配列であることは、上記の[LWC Recipesの実装](https://github.com/trailheadapps/lwc-recipes/blob/main/force-app/main/default/lwc/ldsUtils/ldsUtils.js)の関数コメントと処理で確認できます。

### Q. 使わなくてよいのは、どんなときですか？

エラーの形が分かっている場合や、メッセージを取り出すことが目的ではない場合です。以下はコンポーネント内の処理を抜き出した例で、`this.errorMessage`は画面表示用のプロパティを想定しています。

#### 1. Apexエラーの`message`だけを表示したい場合は？

呼び出しているApexのエラー形式が分かっていて、文言を1つ表示できれば十分な場合です。

```js
try {
    await saveRecord();
} catch (error) {
    this.errorMessage = error?.body?.message || '保存できませんでした。';
}
```

**注意：** 別のAPIのエラーにもこの書き方を流用すると、`body.message`が存在しない場合があります。

**公式資料の該当箇所：** [Salesforce Developers Blog「Understanding the error body payload」](https://developer.salesforce.com/blogs/2020/08/error-handling-best-practices-for-lightning-web-components)に、Apexエラーの`body.message`とAPIごとの`body`の違いが説明されています。**「Apexだけなら直接取得すべき」という公式の指定はありません。** 上のコードは、エラーの形が分かっている場合の簡単な書き方です。

#### 2. エラーコードで処理を分けたい場合は？

利用者への案内や画面の動きを、エラーの種類ごとに変えたい場合です。`reduceErrors`が返すのはメッセージだけなので、分岐には元の`error`を使います。

```js
// getRecord など、error.body が配列のケース
const code = error?.body?.[0]?.errorCode;

if (code === 'INSUFFICIENT_PRIVILEGES') {
    this.errorMessage = 'このレコードを表示する権限がありません。';
} else {
    this.errorMessage = '読み込めませんでした。';
}
```

**注意：** `errorCode`の場所や値は、利用するAPIと実際のエラー応答で確認してください。

**公式資料の該当箇所：** [Salesforce Developers「Handle Errors in Lightning Data Service」](https://developer.salesforce.com/docs/platform/lwc/guide/data-error.html)は、UI APIの読み取りエラーでは`body`が配列になると説明しています。[User Interface API Developer Guide「Error Message」](https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/api_ui.pdf)は`errorCode`を定義し、`INSUFFICIENT_PRIVILEGES`を値の例として挙げています。**「コードで分岐する場合は`reduceErrors`を使わない」という公式の指定はありません。** `reduceErrors`は表示文言を返すため、分岐には元の`error`を使う、という判断です。

#### 3. いつも同じ案内を出したい場合は？

内部のエラー文言を利用者に見せず、決まった案内だけを表示したい場合です。

```js
try {
    await saveRecord();
} catch (error) {
    this.errorMessage = '保存できませんでした。時間をおいて再度お試しください。';
    console.error(error); // 開発時の原因調査用
}
```

**公式資料の該当箇所：** [Salesforce Developers Blog「Displaying and logging errors」](https://developer.salesforce.com/blogs/2020/08/error-handling-best-practices-for-lightning-web-components)は、利用者に分かりやすい表示と`console.error()`による記録に触れています。**「常に固定メッセージを表示する」という公式の推奨はありません。** この例の文言は画面設計に応じた選択です。

#### 4. フォームの入力をチェックしたい場合は？

必須項目など、送信前の入力チェックです。これはSalesforceから返ったエラーを読み取る処理ではありません。

```html
<lightning-input label="名前" required></lightning-input>
```

```js
const input = this.template.querySelector('lightning-input');
input.reportValidity();
if (!input.validity.valid) {
    return; // 入力エラーを表示し、送信しない
}
```

**公式リファレンスの該当箇所：** [`lightning-input`の「Input Validation」](https://developer.salesforce.com/docs/platform/lightning-component-reference/guide/lightning-input.html?type=Develop)に、`required`、`reportValidity()`、`validity.valid`による入力チェックが説明されています。

### Q. 迷ったら、どう判断すればよいですか？

**「返ってきたエラーから表示文言を取り出す」なら`reduceErrors`を検討。** エラーコードでの分岐、固定文言の表示、送信前の入力チェックなら、その目的に合った処理を直接書けば十分です。なお、`reduceErrors`を使う場合でも、取り出した文言が利用者に分かりやすいかは確認しましょう。

---

# 質問：`AuraHandledException`にメッセージを2つ以上入れられますか？

## 回答

**別々のメッセージを、そのまま複数の引数として渡すことはできません。** `AuraHandledException`でLWCに渡す基本形は、1つの文字列メッセージです。ただし、2つ以上の文言を**1つの文字列にまとめて**渡すことはできます。

```apex
List<String> messages = new List<String>{
    '名前を入力してください。',
    'メールアドレスを確認してください。'
};
throw new AuraHandledException(String.join(messages, ' / '));
```

LWC側では、まとめた文言を1つのメッセージとして受け取ります。

```js
catch (error) {
    this.errorMessage = error?.body?.message || '入力を確認してください。';
}
```

**公式資料の該当箇所：** [Apex Exception Classの`AuraHandledException`](https://developer.salesforce.com/docs/platform/apex-ref/references/apex-ref/apex-classes-exception-methods.html)と、[LWC「Handle Errors from Apex」](https://developer.salesforce.com/docs/platform/lwc/guide/apex-error-handling.html)に、カスタムメッセージをJavaScript側へ返す用途が説明されています。複数文言を1つに結合する`String.join`は、[Apex String Classの`join(iterableObj, separator)`](https://developer.salesforce.com/docs/platform/apex-ref/references/apex-ref/apex-methods-system-string.html)に記載されています。

### Q. 2つの文言をLWC側で別々に扱いたい場合は？

その場合は、1つの文字列に結合するだけでは足りません。Apexの戻り値に`List<String>`を含むオブジェクトを用意し、LWCで配列として受け取る方法があります。ただし、この方法は**例外ではなく通常の戻り値**として結果を返す設計です。例外として返す必要がある場合は、メッセージにJSON文字列を入れてLWC側で解析する方法もありますが、受け取る側に追加処理が必要です。

**公式資料の該当箇所：** [LWC「Handle Errors from Apex」](https://developer.salesforce.com/docs/platform/lwc/guide/apex-error-handling.html)の「To return a custom error object instead, create a wrapper class」に、戻り値をオブジェクト化する方法があります。例外のメッセージにJSONを入れて解析する方法は、[Salesforce Developers Blog「Custom error handling」](https://developer.salesforce.com/blogs/2017/09/error-handling-best-practices-lightning-apex)に説明があります。このブログのコードはAura向けなので、LWCでは`error.body.message`から取り出す形に読み替えます。

なお、**`reduceErrors`に結合済みの1つのメッセージを渡しても、自動で元の2件に分けてはくれません。**
