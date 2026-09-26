from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .types import Difficulty, QuestionStatus, QuestionType


class QuestionOption(BaseModel):
    id: UUID
    content: str = Field(min_length=1, max_length=20000)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("选项内容不能为空")
        return value


class QuestionContent(BaseModel):
    type: QuestionType
    content: str = Field(min_length=1, max_length=100000)
    options: list[QuestionOption] = Field(default_factory=list)
    standard_answer: list[str] | StrictBool | str | None = None
    explanation: str | None = Field(default=None, max_length=100000)
    subject: str = Field(min_length=1, max_length=100)
    knowledge_tags: list[str] = Field(default_factory=list, max_length=30)
    difficulty: Difficulty = Difficulty.MEDIUM

    @model_validator(mode="after")
    def validate_content(self):
        if not self.content.strip() or not self.subject.strip():
            raise ValueError("题干与科目不能为空")
        if any(not tag.strip() or len(tag) > 100 for tag in self.knowledge_tags):
            raise ValueError("知识点标签须为1—100个字符")
        if self.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
            ids = [str(option.id) for option in self.options]
            if not 2 <= len(ids) <= 8 or len(set(ids)) != len(ids):
                raise ValueError("选择题需要2—8个稳定且不重复的选项")
            answer = self.standard_answer
            if (
                not isinstance(answer, list)
                or len(set(answer)) != len(answer)
                or not set(answer) <= set(ids)
            ):
                raise ValueError("正确答案必须是不重复的有效选项ID")
            if self.type == QuestionType.SINGLE_CHOICE and len(answer) != 1:
                raise ValueError("单选题须有一个正确答案")
            if self.type == QuestionType.MULTIPLE_CHOICE and len(answer) < 2:
                raise ValueError("多选题须有至少两个正确答案")
        else:
            if self.options:
                raise ValueError("判断题与简答题不接受自定义选项")
            if self.type == QuestionType.TRUE_FALSE and type(self.standard_answer) is not bool:
                raise ValueError("判断题答案必须为布尔值")
            if (
                self.type == QuestionType.SHORT_ANSWER
                and self.standard_answer is not None
                and not isinstance(self.standard_answer, str)
            ):
                raise ValueError("简答题参考答案必须为文本或空")
        return self


class QuestionPublic(QuestionContent):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    creator_id: UUID
    status: QuestionStatus
    version: int
    created_at: datetime
    updated_at: datetime


class VersionRequest(BaseModel):
    version: int = Field(ge=1)


class QuestionUpdate(QuestionContent):
    version: int = Field(ge=1)
